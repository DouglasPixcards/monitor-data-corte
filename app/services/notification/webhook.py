"""Webhooks de mudança de data de corte.

Para cada evento DATA_CORTE_ALTERADA, faz POST do payload a cada URL configurada em
settings.WEBHOOK_URLS. Best-effort: erro de POST é logado e ENGOLIDO — nunca derruba a
coleta. Sem URLs configuradas, é no-op.
"""
from __future__ import annotations

import logging

import requests

from app.core.enums import EventoTipo
from app.core.settings import settings

logger = logging.getLogger(__name__)

# Síncrono na coleta: timeout CURTO pra um webhook lento/blackholed não pendurar a rodada.
_TIMEOUT_S = 5
_ALTERADA = EventoTipo.DATA_CORTE_ALTERADA.value


def _eh_alteracao(evento) -> bool:
    tipo = getattr(evento, "tipo", None)
    return getattr(tipo, "value", tipo) == _ALTERADA


def disparar_mudancas(eventos, urls=None) -> int:
    """POSTa cada DATA_CORTE_ALTERADA em cada webhook. Retorna o nº de POSTs OK."""
    urls = settings.WEBHOOK_URLS if urls is None else urls
    if not urls:
        return 0
    mudancas = [e for e in eventos if _eh_alteracao(e)]
    if not mudancas:
        return 0

    ok = 0
    for e in mudancas:
        payload = {
            "convenio_key": e.convenio_key,
            "processadora": e.processadora,
            "folha": e.folha,
            "mes_atual": e.mes_atual,
            "data_corte_anterior": e.data_corte_anterior,
            "data_corte_nova": e.data_corte_nova,
            "detectado_em": e.detectado_em,
        }
        for url in urls:
            try:
                resp = requests.post(url, json=payload, timeout=_TIMEOUT_S)
                if resp.ok:
                    ok += 1
                else:
                    logger.warning("[webhook] %s respondeu HTTP %s (%s)", url, resp.status_code, e.convenio_key)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[webhook] falha ao notificar %s (%s): %s", url, e.convenio_key, exc)
    return ok
