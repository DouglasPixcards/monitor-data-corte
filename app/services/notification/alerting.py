"""Alerta operacional em tempo real (Slack / webhook genérico) ao fim de cada coleta.

Distinto do webhook de DADOS (mudança de data): aqui é "algo precisa de atenção AGORA".
A severidade vem da categoria do evento; só categorias acionáveis viram alerta (o resto o
e-mail/digest cobre). Best-effort: erro engolido, nunca afeta a coleta. Sem URL = no-op.
"""
from __future__ import annotations

import logging

import requests

from app.core.settings import settings

logger = logging.getLogger(__name__)

_TIMEOUT_S = 8

# categoria do evento → severidade. Fora deste mapa = não alerta por aqui.
_SEVERIDADE = {
    "auth_falhou": "critico",           # falha de login/credencial — categoria MAIS COMUM
    "credencial_expirada": "critico",   # senha expirada — não recupera sozinho
    "portal_mudou": "critico",          # scraper quebrado — precisa de conserto
    "salto_suspeito": "atencao",        # data deu salto improvável — conferir
    "valor_invalido": "atencao",        # valor não-parseável — conferir
}
# Falhas que se repetem TODO dia: não re-alertar persistente/conhecida/gap — só o que é novo.
# (subtipo None — salto_suspeito/valor_invalido — passa: não tem repetição diária de status.)
_SUBTIPO_SILENCIOSO = {"persistente", "conhecida", "gap"}
_EMOJI = {"critico": "🔴", "atencao": "🟡"}
_MAX_POR_SEV = 10


def severidade(categoria: str | None) -> str | None:
    return _SEVERIDADE.get(categoria or "")


def _escape(valor) -> str:
    """Escapa os caracteres especiais do mrkdwn do Slack (&, <, >)."""
    return str(valor).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def montar_texto(eventos: list) -> str | None:
    """Agrupa os eventos acionáveis por severidade num texto. None se não houver nada.

    Ignora falhas persistentes/conhecidas (subtipo) pra não re-alertar o mesmo todo dia.
    """
    buckets: dict[str, list] = {"critico": [], "atencao": []}
    for e in eventos:
        sev = severidade(getattr(e, "categoria", None))
        if sev and getattr(e, "subtipo", None) not in _SUBTIPO_SILENCIOSO:
            buckets[sev].append(e)
    if not any(buckets.values()):
        return None
    linhas = ["*Monitor de Cortes — alerta de coleta*"]
    for sev in ("critico", "atencao"):
        evs = buckets[sev]
        if not evs:
            continue
        linhas.append(f"\n{_EMOJI[sev]} *{sev.upper()}* ({len(evs)})")
        for e in evs[:_MAX_POR_SEV]:
            linhas.append(f"• {_escape(e.convenio_key)} — {_escape(e.categoria)} ({_escape(e.processadora)})")
        if len(evs) > _MAX_POR_SEV:
            linhas.append(f"• … +{len(evs) - _MAX_POR_SEV}")
    return "\n".join(linhas)


def disparar(eventos: list, url: str | None = None) -> bool:
    """Posta o alerta no ALERT_WEBHOOK_URL (payload Slack-compatível `{text}`). No-op sem URL
    ou sem itens acionáveis. Retorna True se o alerta foi enviado (2xx)."""
    url = settings.ALERT_WEBHOOK_URL if url is None else url
    if not url:
        return False
    texto = montar_texto(eventos)
    if not texto:
        return False
    try:
        resp = requests.post(url, json={"text": texto}, timeout=_TIMEOUT_S)
        if resp.ok:
            return True
        logger.warning("[alerting] webhook respondeu HTTP %s", resp.status_code)
    except Exception as exc:  # noqa: BLE001 — best-effort, nunca derruba a coleta
        logger.warning("[alerting] falha ao enviar alerta: %s", exc)
    return False
