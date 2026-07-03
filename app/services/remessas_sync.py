"""Sync monitor → ciclos de remessa (snapshot de data_site).

O monitor re-coleta diariamente e a data pode mudar DEPOIS do ciclo criado. O sync
compara o valor vivo do monitor (mesma montagem do /cortes/atuais) com o snapshot do
ciclo e, quando muda, grava o novo valor + marca `data_site_alterada` (o "vermelho"
da planilha) + auditoria `sync`. Multi-folha com datas divergentes na MESMA
competência → não adivinha: reporta conflito e deixa o ciclo intocado.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.services.consulta_service import montar_dados_convenios
from app.services.remessas_service import (
    auditar,
    competencia_corrente,
    parse_competencia,
)
from app.storage.db import session_scope
from app.storage.remessas_models import CicloRemessaRow, ConvenioRegistroRow
from app.utils.dates import _data_ddmmyyyy

logger = logging.getLogger(__name__)


def sincronizar_data_site(competencia: str | None = None) -> dict:
    """Aplica os valores do monitor aos ciclos da competência (default: corrente)."""
    comp, _ = parse_competencia(competencia or competencia_corrente())

    # Valores vivos do monitor: monitor_key → datas distintas cuja competência derivada = comp.
    datas_por_key: dict[str, set] = {}
    for r in montar_dados_convenios():
        if r.get("competencia") != comp:
            continue
        d = _data_ddmmyyyy(r.get("data_corte"))
        if d is not None:
            datas_por_key.setdefault(r["convenio_key"], set()).add(d)

    atualizados = alterados = sem_valor = 0
    conflitos: list[dict] = []
    agora = datetime.now(timezone.utc)

    from sqlalchemy import select
    with session_scope() as session:
        pares = session.execute(
            select(CicloRemessaRow, ConvenioRegistroRow)
            .join(ConvenioRegistroRow, ConvenioRegistroRow.id == CicloRemessaRow.registro_id)
            .where(CicloRemessaRow.competencia == comp,
                   ConvenioRegistroRow.monitor_key.is_not(None),
                   ConvenioRegistroRow.ativo.is_(True))
        ).all()

        for ciclo, registro in pares:
            datas = datas_por_key.get(registro.monitor_key)
            if not datas:
                sem_valor += 1
                continue
            if len(datas) > 1:
                conflitos.append({
                    "monitor_key": registro.monitor_key, "cod_empr": registro.cod_empr,
                    "datas": sorted(d.isoformat() for d in datas),
                })
                continue
            nova = next(iter(datas))
            if ciclo.data_site == nova:
                continue
            if ciclo.data_site is not None:
                # Mudança REAL sobre um valor que as equipes já viram → vermelho.
                ciclo.data_site_anterior = ciclo.data_site
                ciclo.data_site_alterada = True
                alterados += 1
            auditar(session, entidade="ciclo", entidade_id=ciclo.id, acao="sync",
                    usuario=None, campo="data_site",
                    valor_anterior=ciclo.data_site, valor_novo=nova)
            ciclo.data_site = nova
            ciclo.data_site_origem = "monitor"
            ciclo.data_site_atualizada_em = agora
            ciclo.atualizado_em = agora
            atualizados += 1

    resultado = {"competencia": comp, "atualizados": atualizados, "alterados": alterados,
                 "sem_valor": sem_valor, "conflitos": conflitos}
    logger.info("[remessas-sync] %s", resultado)
    return resultado


def job_sync_periodico() -> None:
    """Wrapper do job agendado — best-effort, nunca derruba o scheduler."""
    try:
        sincronizar_data_site()
    except Exception:  # noqa: BLE001
        logger.exception("[remessas-sync] job periódico falhou")
