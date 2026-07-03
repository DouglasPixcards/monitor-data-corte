"""Regras do módulo de remessas: permissão POR CAMPO, auditoria e projeções.

Toda escrita passa por aqui — o router só traduz HTTP. A allowlist CAMPOS_ESCRITA é a
única fonte da verdade de quem escreve o quê; a UI apenas espelha (cosmético).
Auditoria é gravada NA MESMA transação da mudança (session compartilhada).
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.loader import load_processadoras_config
from app.storage.remessas_models import (
    CicloRemessaRow,
    ConvenioRegistroRow,
    RemessaAuditoriaRow,
    UsuarioRow,
)

logger = logging.getLogger(__name__)

TIPOS_DESCONTO = ("automatico", "remessa")
_SUGESTAO_BANKSOFT_DIAS = 7

_CAMPOS_CONCILIACAO = {
    "data_envio", "valor_enviado", "qtd_contratos",
    "credito_valor", "credito_qtd", "beneficio_valor", "beneficio_qtd",
    "compras_valor", "compras_qtd", "observacao", "validado",
    "data_site",           # contextual: só quando o registro NÃO é monitorado
    "data_site_alterada",  # contextual: só aceita False (o "ciente" do vermelho)
}
_CAMPOS_OPERACOES = {"corte_banksoft"}

CAMPOS_ESCRITA: dict[str, set[str]] = {
    "conciliacao": _CAMPOS_CONCILIACAO,
    "operacoes": _CAMPOS_OPERACOES,
    "admin": _CAMPOS_CONCILIACAO | _CAMPOS_OPERACOES,
}


class PermissaoNegada(Exception):
    def __init__(self, mensagem: str, campos: list[str] | None = None):
        super().__init__(mensagem)
        self.campos = campos or []


class NaoEncontrado(Exception):
    pass


# ── Auditoria ─────────────────────────────────────────────────────────────────

def _str_valor(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return str(v)


def auditar(session: Session, *, entidade: str, entidade_id: str, acao: str,
            usuario: UsuarioRow | None, campo: str | None = None,
            valor_anterior=None, valor_novo=None) -> None:
    session.add(RemessaAuditoriaRow(
        id=str(uuid.uuid4()),
        entidade=entidade, entidade_id=entidade_id, acao=acao, campo=campo,
        valor_anterior=_str_valor(valor_anterior), valor_novo=_str_valor(valor_novo),
        usuario_id=usuario.id if usuario else None,
        usuario_nome=usuario.display_name if usuario else "sistema",
    ))


# ── Competência ───────────────────────────────────────────────────────────────

def parse_competencia(competencia: str) -> tuple[str, date]:
    """'MM/YYYY' (ou 'MM-YYYY') → (canônico 'MM/YYYY', date do dia 1)."""
    normalizada = competencia.strip().replace("-", "/")
    partes = normalizada.split("/")
    if len(partes) != 2:
        raise ValueError(f"Competência inválida: {competencia!r} (esperado MM/YYYY)")
    mes, ano = int(partes[0]), int(partes[1])
    if not (1 <= mes <= 12 and 2000 <= ano <= 2100):
        raise ValueError(f"Competência fora do intervalo: {competencia!r}")
    return f"{mes:02d}/{ano}", date(ano, mes, 1)


def competencia_corrente() -> str:
    hoje = date.today()
    return f"{hoje.month:02d}/{hoje.year}"


def ensure_ciclos(session: Session, competencia: str,
                  usuario: UsuarioRow | None = None) -> int:
    """Cria ciclos em branco (idempotente) para todos os registros ativos na competência."""
    comp, inicio = parse_competencia(competencia)
    existentes = {
        r_id for (r_id,) in session.execute(
            select(CicloRemessaRow.registro_id).where(CicloRemessaRow.competencia == comp)
        )
    }
    criados = 0
    for registro in session.execute(
        select(ConvenioRegistroRow).where(ConvenioRegistroRow.ativo.is_(True))
    ).scalars():
        if registro.id in existentes:
            continue
        ciclo = CicloRemessaRow(
            id=str(uuid.uuid4()), registro_id=registro.id,
            competencia=comp, competencia_inicio=inicio,
        )
        session.add(ciclo)
        auditar(session, entidade="ciclo", entidade_id=ciclo.id, acao="create",
                usuario=usuario, valor_novo=f"{registro.nome} @ {comp}")
        criados += 1
    return criados


# ── Ciclos: escrita com permissão por campo ───────────────────────────────────

def atualizar_ciclo(session: Session, ciclo_id: str, payload: dict,
                    usuario: UsuarioRow) -> tuple[CicloRemessaRow, ConvenioRegistroRow]:
    """Aplica um PATCH parcial. Rejeição TOTAL (sem aplicação parcial) se qualquer
    campo estiver fora da allowlist do papel ou violar regra contextual."""
    ciclo = session.get(CicloRemessaRow, ciclo_id)
    if ciclo is None:
        raise NaoEncontrado(f"Ciclo {ciclo_id!r} não encontrado.")
    registro = session.get(ConvenioRegistroRow, ciclo.registro_id)

    permitidos = CAMPOS_ESCRITA.get(usuario.role, set())
    negados = sorted(set(payload) - permitidos)
    if negados:
        raise PermissaoNegada(
            f"Papel '{usuario.role}' não escreve: {', '.join(negados)}", campos=negados)

    # Regras contextuais (falham ANTES de aplicar qualquer coisa)
    if "data_site" in payload and registro.monitor_key is not None:
        raise PermissaoNegada(
            "data_site é preenchida pelo monitor para convênios monitorados.",
            campos=["data_site"])
    if "data_site_alterada" in payload and payload["data_site_alterada"] is not False:
        raise PermissaoNegada(
            "data_site_alterada só aceita false (ciente).", campos=["data_site_alterada"])

    agora = datetime.now(timezone.utc)
    for campo, novo in payload.items():
        anterior = getattr(ciclo, campo)
        if anterior == novo:
            continue
        setattr(ciclo, campo, novo)
        if campo == "data_site":  # input manual (não-monitorado)
            ciclo.data_site_origem = "manual"
            ciclo.data_site_atualizada_em = agora
        auditar(session, entidade="ciclo", entidade_id=ciclo.id, acao="update",
                usuario=usuario, campo=campo, valor_anterior=anterior, valor_novo=novo)
    ciclo.atualizado_em = agora
    return ciclo, registro


def listar_auditoria(session: Session, entidade: str, entidade_id: str) -> list[dict]:
    linhas = session.execute(
        select(RemessaAuditoriaRow)
        .where(RemessaAuditoriaRow.entidade == entidade,
               RemessaAuditoriaRow.entidade_id == entidade_id)
        .order_by(RemessaAuditoriaRow.ocorrido_em.desc(), RemessaAuditoriaRow.id)
    ).scalars().all()
    return [{
        "ocorrido_em": a.ocorrido_em.isoformat() if a.ocorrido_em else None,
        "usuario_nome": a.usuario_nome, "acao": a.acao, "campo": a.campo,
        "valor_anterior": a.valor_anterior, "valor_novo": a.valor_novo,
    } for a in linhas]


# ── Projeções (o shape por papel é decidido AQUI, no server) ─────────────────

def _iso(v) -> str | None:
    return v.isoformat() if v is not None else None


def _num(v) -> str | None:
    return str(v) if v is not None else None


def status_ciclo(registro: ConvenioRegistroRow, ciclo: CicloRemessaRow) -> str:
    if registro.tipo_desconto == "automatico":
        return "automatico"
    return "enviado" if ciclo.data_envio is not None else "pendente"


def _divergencia(ciclo: CicloRemessaRow) -> dict:
    """Total × soma dos produtos presentes — informativo, nunca bloqueia."""
    valores = [v for v in (ciclo.credito_valor, ciclo.beneficio_valor, ciclo.compras_valor)
               if v is not None]
    qtds = [q for q in (ciclo.credito_qtd, ciclo.beneficio_qtd, ciclo.compras_qtd)
            if q is not None]
    div_valor = (ciclo.valor_enviado is not None and bool(valores)
                 and ciclo.valor_enviado != sum(valores, Decimal("0")))
    div_qtd = (ciclo.qtd_contratos is not None and bool(qtds)
               and ciclo.qtd_contratos != sum(qtds))
    return {"valor": div_valor, "qtd": div_qtd}


def proj_ciclo(ciclo: CicloRemessaRow, registro: ConvenioRegistroRow, role: str) -> dict:
    sugestao = (_iso(ciclo.data_site - timedelta(days=_SUGESTAO_BANKSOFT_DIAS))
                if ciclo.data_site else None)
    a_coletar = registro.monitor_key is not None and ciclo.data_site is None

    base = {
        "id": ciclo.id,
        "competencia": ciclo.competencia,
        "data_site": _iso(ciclo.data_site),
        "data_site_alterada": ciclo.data_site_alterada,
        "corte_banksoft": _iso(ciclo.corte_banksoft),
        "sugestao_corte_banksoft": sugestao,
        "a_coletar": a_coletar,
        "atualizado_em": _iso(ciclo.atualizado_em),
    }
    if role == "operacoes":
        # Visão restrita: os campos da conciliação simplesmente NÃO EXISTEM na resposta.
        base["registro"] = {"cod_empr": registro.cod_empr, "nome": registro.nome}
        return base

    base.update({
        "registro": {
            "id": registro.id, "cod_empr": registro.cod_empr, "nome": registro.nome,
            "link_portal": registro.link_portal, "tipo_desconto": registro.tipo_desconto,
            "produtos": {"credito": registro.prod_credito,
                         "beneficio": registro.prod_beneficio,
                         "compras": registro.prod_compras},
            "monitor_key": registro.monitor_key,
        },
        "data_site_origem": ciclo.data_site_origem,
        "data_site_anterior": _iso(ciclo.data_site_anterior),
        "data_envio": _iso(ciclo.data_envio),
        "valor_enviado": _num(ciclo.valor_enviado),
        "qtd_contratos": ciclo.qtd_contratos,
        "credito_valor": _num(ciclo.credito_valor), "credito_qtd": ciclo.credito_qtd,
        "beneficio_valor": _num(ciclo.beneficio_valor), "beneficio_qtd": ciclo.beneficio_qtd,
        "compras_valor": _num(ciclo.compras_valor), "compras_qtd": ciclo.compras_qtd,
        "observacao": ciclo.observacao,
        "validado": ciclo.validado,
        "status": status_ciclo(registro, ciclo),
        "divergencia": _divergencia(ciclo),
    })
    return base


def listar_ciclos(session: Session, competencia: str, role: str) -> list[dict]:
    comp, _ = parse_competencia(competencia)
    pares = session.execute(
        select(CicloRemessaRow, ConvenioRegistroRow)
        .join(ConvenioRegistroRow, ConvenioRegistroRow.id == CicloRemessaRow.registro_id)
        .where(CicloRemessaRow.competencia == comp)
        .order_by(ConvenioRegistroRow.nome)
    ).all()
    return [proj_ciclo(c, r, role) for c, r in pares]


def listar_competencias(session: Session) -> list[dict]:
    linhas = session.execute(
        select(CicloRemessaRow, ConvenioRegistroRow)
        .join(ConvenioRegistroRow, ConvenioRegistroRow.id == CicloRemessaRow.registro_id)
        .order_by(CicloRemessaRow.competencia_inicio.desc())
    ).all()
    agg: dict[str, dict] = {}
    for ciclo, registro in linhas:
        a = agg.setdefault(ciclo.competencia, {
            "competencia": ciclo.competencia, "total": 0,
            "enviados": 0, "pendentes": 0, "automaticos": 0, "validados": 0,
        })
        a["total"] += 1
        a[{"enviado": "enviados", "pendente": "pendentes",
           "automatico": "automaticos"}[status_ciclo(registro, ciclo)]] += 1
        if ciclo.validado:
            a["validados"] += 1
    return list(agg.values())


# ── Registro (cadastro de convênios) ──────────────────────────────────────────

def _validar_registro(monitor_key: str | None, tipo_desconto: str | None) -> None:
    if tipo_desconto is not None and tipo_desconto not in TIPOS_DESCONTO:
        raise ValueError(f"tipo_desconto inválido: {tipo_desconto!r}")
    if monitor_key is not None:
        convenios = load_processadoras_config()["convenios"]
        if monitor_key not in convenios:
            raise ValueError(f"monitor_key desconhecida: {monitor_key!r}")


def proj_registro(r: ConvenioRegistroRow) -> dict:
    return {
        "id": r.id, "cod_empr": r.cod_empr, "nome": r.nome, "link_portal": r.link_portal,
        "tipo_desconto": r.tipo_desconto,
        "produtos": {"credito": r.prod_credito, "beneficio": r.prod_beneficio,
                     "compras": r.prod_compras},
        "monitor_key": r.monitor_key, "ativo": r.ativo,
    }


def criar_registro(session: Session, dados: dict, usuario: UsuarioRow) -> ConvenioRegistroRow:
    _validar_registro(dados.get("monitor_key"), dados.get("tipo_desconto"))
    registro = ConvenioRegistroRow(
        id=str(uuid.uuid4()),
        cod_empr=dados["cod_empr"], nome=dados["nome"].strip(),
        link_portal=dados.get("link_portal"),
        tipo_desconto=dados["tipo_desconto"],
        prod_credito=dados.get("prod_credito", False),
        prod_beneficio=dados.get("prod_beneficio", False),
        prod_compras=dados.get("prod_compras", False),
        monitor_key=dados.get("monitor_key"),
        ativo=True,
    )
    session.add(registro)
    auditar(session, entidade="registro", entidade_id=registro.id, acao="create",
            usuario=usuario, valor_novo=f"{registro.cod_empr} {registro.nome}")
    return registro


_CAMPOS_REGISTRO = ("cod_empr", "nome", "link_portal", "tipo_desconto",
                    "prod_credito", "prod_beneficio", "prod_compras",
                    "monitor_key", "ativo")


def atualizar_registro(session: Session, registro_id: str, payload: dict,
                       usuario: UsuarioRow) -> ConvenioRegistroRow:
    registro = session.get(ConvenioRegistroRow, registro_id)
    if registro is None:
        raise NaoEncontrado(f"Registro {registro_id!r} não encontrado.")
    _validar_registro(payload.get("monitor_key"), payload.get("tipo_desconto"))
    agora = datetime.now(timezone.utc)
    for campo in _CAMPOS_REGISTRO:
        if campo not in payload:
            continue
        anterior, novo = getattr(registro, campo), payload[campo]
        if anterior == novo:
            continue
        setattr(registro, campo, novo)
        auditar(session, entidade="registro", entidade_id=registro.id, acao="update",
                usuario=usuario, campo=campo, valor_anterior=anterior, valor_novo=novo)
    registro.atualizado_em = agora
    return registro


def monitor_keys_livres(session: Session) -> list[dict]:
    """Convênios do monitor ainda não mapeados a nenhum registro (pro dropdown do admin)."""
    config = load_processadoras_config()["convenios"]
    usadas = {
        k for (k,) in session.execute(
            select(ConvenioRegistroRow.monitor_key)
            .where(ConvenioRegistroRow.monitor_key.is_not(None))
        )
    }
    return [
        {"key": key, "nome": cfg.get("nome", key), "processadora": cfg["processadora"]}
        for key, cfg in sorted(config.items())
        if key not in usadas
    ]
