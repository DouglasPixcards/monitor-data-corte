from __future__ import annotations

from html import escape as _esc

from app.core.enums import EventoTipo
from app.core.models import Evento
from app.services.erro_classifier import CATEGORIA_FRASE

_FOLHA_VIRADA = "virada_competencia"

_DISCLAIMER_VIRADA = (
    "Este dado é uma <strong>estimativa de virada de competência</strong> coletada via API SafeConsig, "
    "não uma data de corte oficial confirmada. "
    "Verifique com a processadora antes de tomar decisões operacionais."
)

_MUTED = "color:#888;font-size:12px;margin:2px 0 0 16px"


def _frase_categoria(categoria: str | None) -> str:
    return CATEGORIA_FRASE.get(categoria or "outro", CATEGORIA_FRASE["outro"])


def _categorizar(eventos: list[Evento]) -> dict:
    """Agrupa eventos nas faixas que o e-mail usa (topo vs rodapé)."""
    mudancas = [e for e in eventos if e.tipo == EventoTipo.DATA_CORTE_ALTERADA]
    novos = [e for e in eventos if e.tipo == EventoTipo.REGISTRO_NOVO]
    recuperados = [e for e in eventos if e.tipo == EventoTipo.RECUPERADO]
    falhas = [e for e in eventos if e.tipo == EventoTipo.ERRO_COLETA]

    sem_dado = [e for e in falhas if e.categoria == "sem_dado"]
    gaps = [e for e in falhas if e.subtipo == "gap"]
    conhecidas = [e for e in falhas if e.subtipo == "conhecida"]
    fora_janela = [e for e in falhas if e.categoria == "fora_janela"]
    credencial_expirada = [e for e in falhas if e.categoria == "credencial_expirada"]
    reais = [e for e in falhas
             if e.categoria not in ("sem_dado", "nao_executou", "fora_janela", "credencial_expirada")
             and e.subtipo != "conhecida"]
    falhas_novas = [e for e in reais if e.subtipo == "falha_nova"]
    persistentes = [e for e in reais if e.subtipo == "persistente"]

    return {
        "mudancas": mudancas, "novos": novos, "recuperados": recuperados,
        "sem_dado": sem_dado, "gaps": gaps, "conhecidas": conhecidas,
        "falhas_novas": falhas_novas, "persistentes": persistentes,
        "fora_janela": fora_janela,
        "credencial_expirada": credencial_expirada,
    }


def _resumo(cat: dict, verificados: int, coletados: int, prefixo: str = "") -> str:
    return (
        f"{prefixo}{verificados} verificados · {coletados} coletados · "
        f"{len(cat['falhas_novas'])} falhas novas · {len(cat['sem_dado'])} sem dado · "
        f"{len(cat['recuperados'])} recuperados · {len(cat['gaps'])} gaps · "
        f"{len(cat['mudancas'])} mudanças de data"
    )


def _precisa_acao(cat: dict) -> bool:
    return bool(cat["mudancas"] or cat["falhas_novas"] or cat["gaps"] or cat["sem_dado"] or cat["credencial_expirada"])


# ── Seções (recebem `rotulo`: callable Evento -> texto do convênio) ────────────

def _secao_mudancas(eventos, rotulo) -> str:
    linhas = "".join(
        f"""
        <tr>
            <td style="padding:6px 12px">{_esc(rotulo(e))}</td>
            <td style="padding:6px 12px">{_esc(e.folha or '-')}</td>
            <td style="padding:6px 12px">{_esc(e.mes_atual or '-')}</td>
            <td style="padding:6px 12px">{_esc(e.data_corte_anterior or '-')}</td>
            <td style="padding:6px 12px"><strong>{_esc(e.data_corte_nova or '-')}</strong></td>
        </tr>"""
        for e in eventos
    )
    return f"""
    <h3 style="margin:16px 0 6px">🔴 Mudanças de data de corte</h3>
    <table border="1" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
        <thead><tr style="background:#f0f0f0">
            <th style="padding:6px 12px">Convênio</th><th style="padding:6px 12px">Folha</th>
            <th style="padding:6px 12px">Mês</th><th style="padding:6px 12px">Antes</th>
            <th style="padding:6px 12px">Depois</th>
        </tr></thead>
        <tbody>{linhas}</tbody>
    </table>"""


def _secao_falhas(titulo, eventos, rotulo) -> str:
    itens = "".join(
        f'<li style="margin:8px 0"><strong>{_esc(rotulo(e))}</strong> — {_esc(_frase_categoria(e.categoria))}'
        f'<div style="{_MUTED}">técnico: {_esc(e.detalhe or "—")}</div></li>'
        for e in eventos
    )
    return f'<h3 style="margin:16px 0 6px">{_esc(titulo)}</h3><ul style="margin:0;padding-left:18px">{itens}</ul>'


def _secao_recuperados(eventos, rotulo) -> str:
    itens = "".join(
        f'<li style="margin:6px 0;color:#2e7d32"><strong>{_esc(rotulo(e))}</strong> — voltou a coletar (estava falhando)</li>'
        for e in eventos
    )
    return f'<h3 style="margin:16px 0 6px">🟢 Recuperados</h3><ul style="margin:0;padding-left:18px">{itens}</ul>'


def _secao_novos(eventos, rotulo) -> str:
    itens = "".join(
        f'<li style="margin:4px 0">{_esc(rotulo(e))} — {_esc(e.folha or "-")} / {_esc(e.mes_atual or "-")}: '
        f'<strong>{_esc(e.data_corte_nova or "-")}</strong></li>'
        for e in eventos
    )
    return f'<h3 style="margin:16px 0 6px">🆕 Novos registros</h3><ul style="margin:0;padding-left:18px">{itens}</ul>'


def _montar_corpo(titulo, resumo, disclaimer_html, cat, rotulo, extra_topo="") -> str:
    partes: list[str] = []
    if cat["mudancas"]:
        partes.append(_secao_mudancas(cat["mudancas"], rotulo))
    if cat["credencial_expirada"]:
        partes.append(_secao_falhas("🔑 Credencial expirada — renovar a senha no portal", cat["credencial_expirada"], rotulo))
    if cat["falhas_novas"]:
        partes.append(_secao_falhas("🔴 Falhas novas", cat["falhas_novas"], rotulo))
    if cat["sem_dado"]:
        partes.append(_secao_falhas("🟡 Sem data de corte (coletou vazio / nunca coletou)", cat["sem_dado"], rotulo))
    if cat["gaps"]:
        partes.append(_secao_falhas("🟠 Não coletados (gap)", cat["gaps"], rotulo))
    if cat["recuperados"]:
        partes.append(_secao_recuperados(cat["recuperados"], rotulo))
    if cat["novos"]:
        partes.append(_secao_novos(cat["novos"], rotulo))

    rodape: list[str] = []
    if cat["persistentes"]:
        rodape.append(_secao_falhas("Falhas persistentes", cat["persistentes"], rotulo))
    if cat["conhecidas"]:
        rodape.append(_secao_falhas("Falhas conhecidas (já mapeadas)", cat["conhecidas"], rotulo))
    if cat["fora_janela"]:
        rodape.append(_secao_falhas("Fora da janela de acesso (coleta adiada)", cat["fora_janela"], rotulo))

    if not partes and not rodape:
        partes.append('<p style="color:#2e7d32">✅ Nenhuma novidade — a coleta rodou normalmente.</p>')

    rodape_html = ""
    if rodape:
        rodape_html = (
            '<hr style="margin:20px 0;border:none;border-top:1px solid #ddd">'
            '<p style="color:#888;font-size:13px;margin:0 0 6px"><em>Conhecidas / persistentes (sem ação imediata):</em></p>'
            + "".join(rodape)
        )

    return f"""
    <html>
    <body style="font-family:sans-serif;color:#222">
        <h2 style="margin:0 0 4px">{_esc(titulo)}</h2>
        <p style="font-size:15px;color:#444;margin:0 0 12px"><strong>{_esc(resumo)}</strong></p>
        {disclaimer_html}
        {extra_topo}
        {"".join(partes)}
        {rodape_html}
    </body>
    </html>
    """


def _disclaimer(cat: dict) -> str:
    if any(e.folha == _FOLHA_VIRADA for e in cat["mudancas"]):
        return (f'<p style="background:#fff8e1;border-left:4px solid #f9a825;padding:10px 14px;margin:12px 0">'
                f'<em>{_DISCLAIMER_VIRADA}</em></p>')
    return ""


class DigestBuilder:
    """Resumo em duas camadas (humano + técnico). ``build`` = 1 processadora;
    ``build_agregado`` = 1 e-mail diário consolidando todas as processadoras."""

    @staticmethod
    def build(processadora: str, eventos: list[Evento], resultado_lote: dict | None = None) -> tuple[str, str]:
        resultado_lote = resultado_lote or {}
        nome_map = {
            c["convenio_key"]: (c.get("convenio_nome") or c["convenio_key"])
            for c in resultado_lote.get("convenios", [])
        }
        cat = _categorizar(eventos)
        verificados = resultado_lote.get("total_convenios", 0)
        coletados = resultado_lote.get("success_count", 0)
        resumo = _resumo(cat, verificados, coletados)

        marca = "[Ação]" if _precisa_acao(cat) else ("[OK]" if cat["recuperados"] else "[OK]")
        prefixo = "Datas de corte" if _precisa_acao(cat) or cat["recuperados"] else "Resumo diário"
        assunto = f"{marca} {prefixo} — {processadora}: {resumo}"

        def rotulo(e: Evento) -> str:
            return nome_map.get(e.convenio_key, e.convenio_key)

        corpo = _montar_corpo(f"Resumo diário — {processadora}", resumo, _disclaimer(cat), cat, rotulo)
        return assunto, corpo

    @staticmethod
    def build_agregado(resultados: list) -> tuple[str, str]:
        """``resultados``: lista de ResultadoColeta (processadora, execucao, eventos, resultado_lote)."""
        nome_map: dict[str, str] = {}
        all_eventos: list[Evento] = []
        verificados = coletados = 0
        for r in resultados:
            lote = r.resultado_lote or {}
            for c in lote.get("convenios", []):
                nome_map[c["convenio_key"]] = c.get("convenio_nome") or c["convenio_key"]
            all_eventos.extend(r.eventos)
            verificados += lote.get("total_convenios", 0)
            coletados += lote.get("success_count", 0)

        cat = _categorizar(all_eventos)
        n_proc = len(resultados)
        resumo = _resumo(cat, verificados, coletados, prefixo=f"{n_proc} processadoras · ")

        marca = "[Ação]" if _precisa_acao(cat) else "[OK]"
        assunto = f"{marca} Coleta diária — {resumo}"

        def rotulo(e: Evento) -> str:
            return f"[{e.processadora}] {nome_map.get(e.convenio_key, e.convenio_key)}"

        tabela = DigestBuilder._tabela_processadoras(resultados)
        corpo = _montar_corpo("Coleta diária consolidada", resumo, _disclaimer(cat), cat, rotulo, extra_topo=tabela)
        return assunto, corpo

    @staticmethod
    def _tabela_processadoras(resultados: list) -> str:
        linhas = []
        for r in sorted(resultados, key=lambda x: x.processadora):
            lote = r.resultado_lote or {}
            cat_r = _categorizar(r.eventos)
            status = (r.execucao.status if r.execucao else lote.get("status", ""))
            icon = {"ok": "✓", "partial_success": "⚠", "erro": "✗"}.get(status, "•")
            total = lote.get("total_convenios", 0)
            ok = lote.get("success_count", 0)
            linhas.append(
                f'<tr>'
                f'<td style="padding:4px 10px">{icon} {_esc(r.processadora)}</td>'
                f'<td style="padding:4px 10px;text-align:center">{ok}/{total}</td>'
                f'<td style="padding:4px 10px;text-align:center">{len(cat_r["falhas_novas"])}</td>'
                f'<td style="padding:4px 10px;text-align:center">{len(cat_r["sem_dado"])}</td>'
                f'<td style="padding:4px 10px;text-align:center">{len(cat_r["mudancas"])}</td>'
                f'</tr>'
            )
        return f"""
        <h3 style="margin:14px 0 6px">Por processadora</h3>
        <table border="1" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:13px">
            <thead><tr style="background:#f0f0f0">
                <th style="padding:4px 10px;text-align:left">Processadora</th>
                <th style="padding:4px 10px">Coletados</th>
                <th style="padding:4px 10px">Falhas novas</th>
                <th style="padding:4px 10px">Sem dado</th>
                <th style="padding:4px 10px">Mudanças</th>
            </tr></thead>
            <tbody>{"".join(linhas)}</tbody>
        </table>"""
