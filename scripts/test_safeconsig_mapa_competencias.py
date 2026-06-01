"""Mapa exploratório de competências — SafeConsig.

Consulta o endpoint /contrato/mesPrimeiroDesconto/consultar para uma sequência
de datas e exibe quando a competência retornada muda.

ATENÇÃO: Este endpoint NÃO retorna data de corte oficial.
         Ele retorna a competência prevista do primeiro desconto para uma data
         hipotética. A virada de competência observada aqui é um INDÍCIO —
         não uma confirmação — do corte. Valide com o portal antes de usar
         como regra oficial.

Uso:
    python scripts/test_safeconsig_mapa_competencias.py
    python scripts/test_safeconsig_mapa_competencias.py --env-key SAFECONSIG_HML
    python scripts/test_safeconsig_mapa_competencias.py --env-key SAFECONSIG_PROD_SAOJOAODOSPATOS
    python scripts/test_safeconsig_mapa_competencias.py --env-key SAFECONSIG_HML 2026-06-01 2026-06-30 23:30:00

Requer no .env as variáveis do perfil escolhido:
    {ENV_KEY}_BASE_URL
    {ENV_KEY}_ID_CONVENIO
    {ENV_KEY}_USERNAME
    {ENV_KEY}_PASSWORD
"""
from __future__ import annotations

import argparse
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


def _default_data_inicial() -> str:
    hoje = date.today()
    return hoje.replace(day=1).isoformat()


def _default_data_final() -> str:
    hoje = date.today()
    ultimo_dia = calendar.monthrange(hoje.year, hoje.month)[1]
    return hoje.replace(day=ultimo_dia).isoformat()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mapa de competências SafeConsig.")
    parser.add_argument(
        "--env-key",
        default="SAFECONSIG_HML",
        metavar="KEY",
        help="Prefixo das variáveis de ambiente (default: SAFECONSIG_HML)",
    )
    parser.add_argument(
        "data_inicial",
        nargs="?",
        default=None,
        help="Data inicial no formato YYYY-MM-DD (default: 1º do mês atual)",
    )
    parser.add_argument(
        "data_final",
        nargs="?",
        default=None,
        help="Data final no formato YYYY-MM-DD (default: último dia do mês atual)",
    )
    parser.add_argument(
        "horario",
        nargs="?",
        default="10:00:00",
        help="Horário usado em todas as consultas (default: 10:00:00)",
    )
    return parser.parse_args()


def _iter_datas(data_inicial: str, data_final: str):
    inicio = date.fromisoformat(data_inicial)
    fim = date.fromisoformat(data_final)
    atual = inicio
    while atual <= fim:
        yield atual
        atual += timedelta(days=1)


def main() -> int:
    args = _parse_args()
    data_inicial = args.data_inicial or _default_data_inicial()
    data_final = args.data_final or _default_data_final()
    horario = args.horario

    print(f"Perfil:   {args.env_key}")
    print(f"Período:  {data_inicial} → {data_final}")
    print(f"Horário:  {horario}")
    print(f"Endpoint: /contrato/mesPrimeiroDesconto/consultar")
    print()

    try:
        config = SafeConsigConfig.from_env(args.env_key)
    except IntegrationError as exc:
        print(f"[ERRO] Configuração inválida para {args.env_key!r}: {exc}", file=sys.stderr)
        return 1

    client = SafeConsigClient(config)
    try:
        client.autenticar()
    except IntegrationError as exc:
        print(f"[ERRO] Falha na autenticação ({args.env_key}): {exc}", file=sys.stderr)
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
