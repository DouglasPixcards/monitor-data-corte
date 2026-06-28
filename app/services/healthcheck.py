"""Dead-man's switch — "quem vigia o vigia".

Pinga um serviço de uptime externo (ex.: healthchecks.io) ao fim de cada ciclo de coleta.
Se o ciclo NÃO rodar (cron/runner caiu, DB fora, processo morto), o ping não chega e o
serviço externo alerta — INDEPENDENTE do próprio monitor. Best-effort: erro de ping nunca
afeta a coleta. Sem HEALTHCHECK_URL configurada, é no-op.
"""
from __future__ import annotations

import logging

import requests

from app.core.settings import settings

logger = logging.getLogger(__name__)

_TIMEOUT_S = 8


def pingar(sucesso: bool = True, url: str | None = None) -> bool:
    """Pinga o HEALTHCHECK_URL — sufixo '/fail' quando sucesso=False. No-op sem URL.

    Retorna True se o ping foi aceito (2xx).
    """
    url = settings.HEALTHCHECK_URL if url is None else url
    if not url:
        return False
    destino = url if sucesso else url.rstrip("/") + "/fail"
    try:
        resp = requests.get(destino, timeout=_TIMEOUT_S)
        if resp.ok:
            return True
        logger.warning("[healthcheck] %s respondeu HTTP %s", destino, resp.status_code)
    except Exception as exc:  # noqa: BLE001 — ping é best-effort, nunca derruba a coleta
        logger.warning("[healthcheck] falha ao pingar: %s", exc)
    return False
