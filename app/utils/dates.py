from __future__ import annotations

import re
from datetime import date, datetime

_MESES_EN: dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


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

    # "10 Jun", "5 Jan" — dia + mês abreviado em inglês (ConsigNet)
    m = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]{3,})", data_corte)
    if m:
        dia = int(m.group(1))
        mes = _MESES_EN.get(m.group(2).lower()[:3])
        if mes:
            ano = _ano_ref(coletado_em)
            return f"{dia:02d}/{mes:02d}/{ano}"

    # Só o dia — infere mês/ano pela regra de negócio
    m = re.fullmatch(r"(\d{1,2})", data_corte)
    if m:
        dia = int(m.group(1))
        mes, ano = _mes_ano_pelo_dia(dia, coletado_em)
        if mes and ano:
            return f"{dia:02d}/{mes:02d}/{ano}"

    return data_corte


def _ano_ref(coletado_em: str | None) -> int:
    if coletado_em:
        try:
            return datetime.fromisoformat(coletado_em.replace("Z", "+00:00")).year
        except Exception:
            pass
    return datetime.now().year


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


def validar_data_corte(valor: str | None, coletado_em: str | None = None) -> bool:
    """True se `valor` é uma data de corte PLAUSÍVEL (não garbage).

    - ``DD/MM/YYYY``: data de calendário REAL (rejeita 31/02) e ano dentro de
      ``[ano_coleta - 1 .. ano_coleta + 1]``.
    - ``MM/YYYY``: competência/estimativa (ex.: SafeConsig), mês 1–12 e ano plausível.
    - ``None``, vazio ou qualquer outra forma → ``False``.

    O ano de referência vem de ``coletado_em`` (mesma extração de ``normalizar_data_corte``);
    passe-o nos testes para um resultado determinístico.
    """
    if not valor:
        return False
    v = valor.strip()
    # Ano de referência da coleta — SEM fallback para datetime.now() (mantém a função
    # pura/determinística). Sem coletado_em parseável, a janela de ano é dispensada.
    ano_ref: int | None = None
    if coletado_em:
        try:
            ano_ref = datetime.fromisoformat(coletado_em.replace("Z", "+00:00")).year
        except (ValueError, TypeError):
            ano_ref = None

    def _ano_ok(ano: int) -> bool:
        return ano_ref is None or ano_ref - 1 <= ano <= ano_ref + 1

    # Competência MM/YYYY (estimativa)
    m = re.fullmatch(r"(\d{1,2})/(\d{4})", v)
    if m:
        mes, ano = int(m.group(1)), int(m.group(2))
        return 1 <= mes <= 12 and _ano_ok(ano)

    # Data DD/MM/YYYY de calendário real
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", v)
    if m:
        dia, mes, ano = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if not _ano_ok(ano):
            return False
        try:
            datetime(ano, mes, dia)
            return True
        except ValueError:
            return False

    return False


# Salto plausível (em dias) de uma data de corte entre coletas, para a MESMA
# competência. Acima disso, a mudança é improvável → sinal "conferir".
_MAX_SALTO_DIAS = 45


def _data_ddmmyyyy(valor: str | None) -> date | None:
    """Converte 'DD/MM/YYYY' real numa date; None para qualquer outra forma."""
    if not valor:
        return None
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", valor.strip())
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def salto_data_corte_suspeito(anterior: str | None, atual: str | None) -> bool:
    """True se o salto em dias entre duas data_corte DD/MM/YYYY excede _MAX_SALTO_DIAS.

    Só avalia datas DD/MM/YYYY reais; MM/YYYY (competência), None ou garbage → False
    (não avalia — reconciliação é só para datas precisas).
    """
    da = _data_ddmmyyyy(anterior)
    db = _data_ddmmyyyy(atual)
    if da is None or db is None:
        return False
    return abs((db - da).days) > _MAX_SALTO_DIAS
