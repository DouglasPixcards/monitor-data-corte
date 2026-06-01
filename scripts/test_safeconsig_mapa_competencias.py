"""Mapa exploratório de competências — SafeConsig HML.

Consulta o endpoint /contrato/mesPrimeiroDesconto/consultar para uma sequência
de datas e exibe quando a competência retornada muda.

ATENÇÃO: Este endpoint NÃO retorna data de corte oficial.
         Ele retorna a competência prevista do primeiro desconto para uma data
         hipotética. A virada de competência observada aqui é um INDÍCIO —
         não uma confirmação — do corte. Valide com o portal antes de usar
         como regra oficial.

Configuração (altere as variáveis abaixo ou passe como args):
    DATA_INICIAL   — primeira data a consultar  (default: 1º do mês atual)
    DATA_FINAL     — última data a consultar    (default: último dia do mês)
    HORARIO        — horário usado em todas as consultas (default: "10:00:00")

Uso:
    python scripts/test_safeconsig_mapa_competencias.py
    python scripts/test_safeconsig_mapa_competencias.py 2025-06-01 2025-06-30 23:30:00

Requer no .env:
    SAFECONSIG_HML_BASE_URL
    SAFECONSIG_HML_ID_CONVENIO
    SAFECONSIG_HML_USERNAME
    SAFECONSIG_HML_PASSWORD
"""
from __future__ import annotations

import calendar
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

from dotenv import load_dotenv
load_dotenv()

from app.integrations.processors.base.exceptions import IntegrationError
from app.integrations.processors.safeconsig.client import SafeConsigClient
from app.integrations.processors.safeconsig.config import SafeConsigConfig

# ── Configuração ──────────────────────────────────────────────────────────────

def _default_data_inicial() -> str:
    hoje = date.today()
    return hoje.replace(day=1).isoformat()

def _default_data_final() -> str:
    hoje = date.today()
    ultimo_dia = calendar.monthrange(hoje.year, hoje.month)[1]
    return hoje.replace(day=ultimo_dia).isoformat()

def _parse_args() -> tuple[str, str, str]:
    args = sys.argv[1:]
    data_inicial = args[0] if len(args) > 0 else _default_data_inicial()
    data_final   = args[1] if len(args) > 1 else _default_data_final()
    horario      = args[2] if len(args) > 2 else "10:00:00"
    return data_inicial, data_final, horario

def _iter_datas(data_inicial: str, data_final: str):
    inicio = date.fromisoformat(data_inicial)
    fim    = date.fromisoformat(data_final)
    atual  = inicio
    while atual <= fim:
        yield atual
        atual += timedelta(days=1)

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    data_inicial, data_final, horario = _parse_args()

    print(f"Período:  {data_inicial} → {data_final}")
    print(f"Horário:  {horario}")
    print(f"Endpoint: /contrato/mesPrimeiroDesconto/consultar")
    print()

    try:
        config = SafeConsigConfig.from_env("SAFECONSIG_HML")
    except IntegrationError as exc:
        print(f"[ERRO] Configuração inválida: {exc}", file=sys.stderr)
        return 1

    client = SafeConsigClient(config)
    try:
        client.autenticar()
    except IntegrationError as exc:
        print(f"[ERRO] Falha na autenticação: {exc}", file=sys.stderr)
        return 1

    print(f"{'DATA':12}  {'COMPETENCIA':12}  OBSERVAÇÃO")
    print("-" * 45)

    competencia_anterior: str | None = None
    viradas: list[tuple[str, str, str]] = []

    for dia in _iter_datas(data_inicial, data_final):
        data_hora = f"{dia.isoformat()} {horario}"
        try:
            resultado = client.consultar_mes_primeiro_desconto(data_hora)
        except IntegrationError as exc:
            print(f"{dia.isoformat():<12}  {'ERRO':12}  {exc}")
            continue

        competencia = resultado.get("competencia") or "N/A"
        observacao = ""

        if competencia_anterior is not None and competencia != competencia_anterior:
            observacao = f"*** VIRADA: {competencia_anterior} → {competencia}"
            viradas.append((dia.isoformat(), competencia_anterior, competencia))

        print(f"{dia.isoformat():<12}  {competencia:<12}  {observacao}")
        competencia_anterior = competencia

    print()
    if viradas:
        print("── Possíveis viradas de competência (virada_competencia) ────────────")
        for data_virada, de, para in viradas:
            print(f"  {data_virada}  {de} → {para}")
        print()
        print("ATENÇÃO: virada de competência ≠ data de corte oficial.")
        print("         Confirme com o portal antes de usar como regra de negócio.")
    else:
        print("Nenhuma virada de competência detectada no período.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
