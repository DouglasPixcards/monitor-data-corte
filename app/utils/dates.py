from __future__ import annotations

import re
from datetime import datetime


def normalizar_data_corte(
    data_corte: str | None,
    mes_atual: str | None = None,
    coletado_em: str | None = None,
) -> str | None:
    """Normaliza data_corte para o formato DD/MM/YYYY.

    Aceita:
      - "DD/MM/YYYY"  → retorna com zero-padding
      - "DD/MM/YY"    → converte ano para 4 dígitos
      - "DD"          → infere mês/ano pela data de coleta:
                         se dia >= dia de hoje → mês atual
                         se dia <  dia de hoje → próximo mês (já passou)
    """
    if not data_corte:
        return None

    data_corte = data_corte.strip()

    # DD/MM/YYYY
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", data_corte)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{d:02d}/{mo:02d}/{y}"

    # DD/MM/YY
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2})", data_corte)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), 2000 + int(m.group(3))
        return f"{d:02d}/{mo:02d}/{y}"

    # Só o dia — infere mês/ano pela regra de negócio
    m = re.fullmatch(r"(\d{1,2})", data_corte)
    if m:
        dia = int(m.group(1))
        mes, ano = _mes_ano_pelo_dia(dia, coletado_em)
        if mes and ano:
            return f"{dia:02d}/{mes:02d}/{ano}"

    return data_corte


def _mes_ano_pelo_dia(dia: int, coletado_em: str | None) -> tuple[int | None, int | None]:
    """Determina mês/ano do corte comparando o dia com a data de coleta.

    Se o dia de corte ainda não chegou (ou é hoje) → mês da coleta.
    Se já passou → próximo mês.
    """
    ref: datetime | None = None
    if coletado_em:
        try:
            ref = datetime.fromisoformat(coletado_em.replace("Z", "+00:00"))
        except Exception:
            pass

    if ref is None:
        ref = datetime.now()

    if dia >= ref.day:
        return ref.month, ref.year

    # Dia já passou — próximo mês
    if ref.month == 12:
        return 1, ref.year + 1
    return ref.month + 1, ref.year
