"""Seed ÚNICO do cadastro de convênios (convenios_registro) a partir da planilha da conciliação.

- DRY-RUN por default: imprime a tabela de revisão (incl. auto-match de monitor_key por nome,
  com score). Nada é gravado sem --apply.
- Idempotente: cod_empr já cadastrado é PULADO (seed é uma vez; depois o admin usa o painel).
- Lê do xlsx da conciliação: cod_empr, nome, produtos (pelas colunas de valores), observação
  (heurística fraca de "automático" — SEMPRE revisar no dry-run).
- Lê links_processadoras.xlsx APENAS as colunas CONVENIO e URL (NUNCA login/senha).

Uso:
    python scripts/seed_convenios_registro.py --planilha controle.xlsx [--links links_processadoras.xlsx]
    python scripts/seed_convenios_registro.py --planilha controle.xlsx --apply [--competencia 07/2026]
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
import uuid
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ── Mapeamento de colunas da planilha (EDITE aqui se o cabeçalho mudar) ────────
COLUNAS = {
    "cod_empr": "cod_empr",
    "nome": "Convenio",
    "observacao": "observacao",
    "credito": "Crédito",
    "beneficio": "Benefício",
    "compras": "Compras",
}
_MATCH_PROPOE = 0.85
_MATCH_REVISA = 0.60
_STOPWORDS = ("pref de ", "pref ", "prefeitura de ", "prefeitura ", "gov de ", "gov ",
              "governo de ", "governo do ", "governo da ", "municipio de ", "município de ")


def normalizar_nome(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    for w in _STOPWORDS:
        s = s.replace(w, " ")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _variantes(nome_normalizado: str) -> list[str]:
    """O nome e o nome sem o sufixo de UF ('contagem mg' → também 'contagem')."""
    variantes = [nome_normalizado]
    tokens = nome_normalizado.split()
    if len(tokens) > 1 and len(tokens[-1]) == 2:  # UF no fim
        variantes.append(" ".join(tokens[:-1]))
    return variantes


def melhor_match(nome: str, candidatos: dict[str, str]) -> tuple[str | None, float]:
    """candidatos: monitor_key -> nome. Retorna (key, score) do melhor match por nome."""
    alvos = _variantes(normalizar_nome(nome))
    melhor, melhor_score = None, 0.0
    for key, cand_nome in candidatos.items():
        for cand in (normalizar_nome(cand_nome), normalizar_nome(key.replace("_", " "))):
            for alvo in alvos:
                score = SequenceMatcher(None, alvo, cand).ratio()
                if score > melhor_score:
                    melhor, melhor_score = key, score
    return melhor, round(melhor_score, 2)


def parece_automatico(observacao: str | None) -> bool:
    """Heurística FRACA (só sugestão pro dry-run): 'desc automatico', 'sem remessa'..."""
    o = normalizar_nome(observacao or "")
    return any(t in o for t in ("desc automatico", "desconto automatico", "sem remessa"))


def carregar_links(path: Path) -> dict[str, str]:
    """links_processadoras.xlsx → nome normalizado → URL (SÓ colunas CONVENIO/URL)."""
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True)
    ws = wb.active
    cab = [str(c.value or "").strip().upper() for c in ws[1]]
    try:
        i_conv, i_url = cab.index("CONVENIO"), cab.index("URL")
    except ValueError:
        print(f"AVISO: {path} sem colunas CONVENIO/URL — links ignorados.")
        return {}
    return {
        normalizar_nome(str(row[i_conv])): str(row[i_url]).strip()
        for row in ws.iter_rows(min_row=2, values_only=True)
        if row[i_conv] and row[i_url]
    }


def carregar_planilha(path: Path) -> list[dict]:
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    cab = {str(c.value or "").strip(): i for i, c in enumerate(ws[1])}
    faltando = [v for v in (COLUNAS["cod_empr"], COLUNAS["nome"]) if v not in cab]
    if faltando:
        raise SystemExit(f"ERRO: colunas obrigatórias ausentes na planilha: {faltando}. "
                         f"Cabeçalho visto: {list(cab)}")

    def val(row, chave):
        idx = cab.get(COLUNAS[chave])
        return row[idx] if idx is not None and idx < len(row) else None

    linhas = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        cod, nome = val(row, "cod_empr"), val(row, "nome")
        if cod is None or nome is None or str(nome).strip() == "":
            continue
        linhas.append({
            "cod_empr": int(cod),
            "nome": str(nome).strip(),
            "observacao": str(val(row, "observacao") or "").strip() or None,
            "prod_credito": val(row, "credito") is not None,
            "prod_beneficio": val(row, "beneficio") is not None,
            "prod_compras": val(row, "compras") is not None,
        })
    return linhas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--planilha", required=True, type=Path)
    parser.add_argument("--links", type=Path, default=None)
    parser.add_argument("--apply", action="store_true", help="Grava (default = dry-run)")
    parser.add_argument("--competencia", default=None,
                        help="Abre os ciclos desta competência após o seed (MM/YYYY)")
    args = parser.parse_args()

    from app.core.loader import load_processadoras_config

    monitor = {k: cfg.get("nome", k)
               for k, cfg in load_processadoras_config()["convenios"].items()}
    linhas = carregar_planilha(args.planilha)
    links = carregar_links(args.links) if args.links else {}

    print(f"Planilha: {len(linhas)} convênios | monitor: {len(monitor)} keys | "
          f"links: {len(links)}\n")
    print(f"{'COD':>4} {'NOME':<40} {'TIPO':<10} {'PROD':<12} {'MATCH MONITOR':<28} {'LINK'}")
    print("-" * 110)

    usados: dict[str, int] = {}
    for l in linhas:
        key, score = melhor_match(l["nome"], monitor)
        if score >= _MATCH_PROPOE:
            l["monitor_key"], status = key, f"{key} ({score}) ✓"
        elif score >= _MATCH_REVISA:
            l["monitor_key"], status = None, f"{key}? ({score}) REVISAR"
        else:
            l["monitor_key"], status = None, "—"
        if l["monitor_key"]:
            usados.setdefault(l["monitor_key"], 0)
            usados[l["monitor_key"]] += 1
        l["tipo_desconto"] = "automatico" if parece_automatico(l["observacao"]) else "remessa"
        l["link_portal"] = links.get(normalizar_nome(l["nome"]))
        prods = "".join(p[0].upper() for p in ("credito", "beneficio", "compras")
                        if l[f"prod_{p}"]) or "—"
        print(f"{l['cod_empr']:>4} {l['nome'][:40]:<40} {l['tipo_desconto']:<10} "
              f"{prods:<12} {status:<28} {'✓' if l['link_portal'] else ''}")

    # 1:1 estrito: dois cod_empr no MESMO monitor_key → nenhum leva (revisão manual)
    duplicados = {k for k, n in usados.items() if n > 1}
    if duplicados:
        print(f"\n⚠️ monitor_keys com MAIS de um match (1:1 violado — ninguém leva): {duplicados}")
        for l in linhas:
            if l["monitor_key"] in duplicados:
                l["monitor_key"] = None

    if not args.apply:
        print("\n[dry-run] Nada gravado. Revise a tabela e rode com --apply.")
        return 0

    from sqlalchemy import select

    from app.services.remessas_service import auditar, ensure_ciclos
    from app.storage import db
    from app.storage.remessas_models import ConvenioRegistroRow

    db.assert_ready()
    criados = pulados = 0
    with db.session_scope() as session:
        existentes = {c for (c,) in session.execute(select(ConvenioRegistroRow.cod_empr))}
        keys_usadas = {k for (k,) in session.execute(
            select(ConvenioRegistroRow.monitor_key)
            .where(ConvenioRegistroRow.monitor_key.is_not(None)))}
        for l in linhas:
            if l["cod_empr"] in existentes:
                pulados += 1
                continue
            mk = l["monitor_key"] if l["monitor_key"] not in keys_usadas else None
            registro = ConvenioRegistroRow(
                id=str(uuid.uuid4()), cod_empr=l["cod_empr"], nome=l["nome"],
                link_portal=l["link_portal"], tipo_desconto=l["tipo_desconto"],
                prod_credito=l["prod_credito"], prod_beneficio=l["prod_beneficio"],
                prod_compras=l["prod_compras"], monitor_key=mk, ativo=True,
            )
            session.add(registro)
            if mk:
                keys_usadas.add(mk)
            auditar(session, entidade="registro", entidade_id=registro.id, acao="create",
                    usuario=None, valor_novo=f"seed: {l['cod_empr']} {l['nome']}")
            criados += 1
        if args.competencia:
            abertos = ensure_ciclos(session, args.competencia, usuario=None)
            print(f"\nCompetência {args.competencia}: {abertos} ciclo(s) aberto(s).")

    print(f"\n✓ Seed: {criados} criado(s), {pulados} já existiam (pulados).")
    if args.competencia:
        print("Rode o sync no painel (↻ Sync) para puxar as datas do monitor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
