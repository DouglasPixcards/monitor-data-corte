"""Janela de acesso de coleta do ConsigUp.

O portal ConsigUp (sistema.consigup.com.br) só permite acesso em dias úteis,
horário comercial (08:00–17:00, America/Sao_Paulo). Fora disso a coleta é
PULADA — não se toca o portal. Específico do consigup; não é um sistema genérico.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("America/Sao_Paulo")
except Exception:  # tzdata ausente (ex.: Windows sem o pacote) → offset fixo
    _TZ = timezone(timedelta(hours=-3))

PROCESSADORA = "consigup"
JANELA_INICIO = time(8, 0)
JANELA_FIM = time(17, 0)
MARGEM_MIN = 15  # corte efetivo = 16:45


def _agora_local() -> datetime:
    """Hora atual no fuso do portal. Patchável nos testes."""
    return datetime.now(_TZ)


def _corte_efetivo() -> time:
    base = datetime(2000, 1, 1, JANELA_FIM.hour, JANELA_FIM.minute)
    return (base - timedelta(minutes=MARGEM_MIN)).time()


def dentro_da_janela_consigup(agora: datetime | None = None) -> bool:
    """True se ``agora`` está na janela: dia útil (seg–sex) e 08:00 ≤ hora < 16:45."""
    agora = agora if agora is not None else _agora_local()
    if agora.weekday() >= 5:  # 5=sábado, 6=domingo — fim de semana não coleta
        return False
    t = agora.time()
    return JANELA_INICIO <= t < _corte_efetivo()
