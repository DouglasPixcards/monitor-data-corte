"""Confiança da data de corte por convênio, a partir da frequência de mudanças.

Um convênio cuja data de corte muda muito numa janela é menos confiável (instável);
um que não muda é estável. Derivado dos eventos DATA_CORTE_ALTERADA.
"""
from __future__ import annotations

import re

# Janela padrão (dias) para avaliar a estabilidade.
JANELA_DIAS = 90


def _dia(valor: str | None) -> int | None:
    """Dia do mês de um 'DD/MM/YYYY'; None para qualquer outra forma (MM/YYYY etc.)."""
    if not valor:
        return None
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", valor.strip())
    return int(m.group(1)) if m else None


def mudou_dia_corte(anterior: str | None, nova: str | None) -> bool:
    """True só quando o DIA do mês da data de corte mudou (entre dois DD/MM/YYYY).

    Avanço normal de mês (mesmo dia, ex.: 10/05 → 10/06) ou competência (MM/YYYY)
    NÃO contam como instabilidade — são progressão esperada, não mudança do corte.
    """
    da, dn = _dia(anterior), _dia(nova)
    return da is not None and dn is not None and da != dn


def classificar_confianca(mudancas: int) -> str:
    """Classifica a confiança pela contagem de mudanças na janela.

    - 0 mudanças  → "estavel"
    - 1–2         → "media"
    - >= 3        → "instavel"
    """
    if mudancas <= 0:
        return "estavel"
    if mudancas <= 2:
        return "media"
    return "instavel"
