"""Serviço de agendamento do runner diário (container dedicado).

Mantém o processo vivo e dispara `run_daily_collection.main()` no horário
`COLETA_HORARIO` (HH:MM), todos os dias. Reaproveita TODA a lógica do runner
(retry paralelo + known_failure) — este wrapper só agenda.

Variáveis de ambiente:
    COLETA_HORARIO    Horário diário da coleta no formato HH:MM (ex: "06:00").
    RUN_ON_START      Se "true", roda uma coleta imediatamente no boot.

Comportamento:
    - RUN_ON_START=true            → coleta imediata no boot.
    - COLETA_HORARIO definido      → agenda diariamente e bloqueia.
    - Nenhum dos dois              → loga aviso e encerra (nada a fazer).
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# raiz do projeto + diretório scripts/ no path (para importar run_daily_collection)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("run_scheduler_service")

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from run_daily_collection import main as run_collection


def _bool_env(key: str) -> bool:
    return os.getenv(key, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_horario(horario: str) -> tuple[int, int]:
    partes = horario.strip().split(":")
    if len(partes) != 2:
        raise ValueError(horario)
    hora, minuto = int(partes[0]), int(partes[1])
    if not (0 <= hora <= 23 and 0 <= minuto <= 59):
        raise ValueError(horario)
    return hora, minuto


def _coletar() -> None:
    logger.info("[SchedulerService] Disparando coleta diária...")
    try:
        codigo = run_collection()
        logger.info("[SchedulerService] Coleta finalizada (exit=%s).", codigo)
    except Exception:
        logger.exception("[SchedulerService] Coleta falhou com exceção não tratada.")


def main() -> int:
    horario = os.getenv("COLETA_HORARIO", "").strip()
    run_on_start = _bool_env("RUN_ON_START")

    if run_on_start:
        logger.info("[SchedulerService] RUN_ON_START ativo — coleta imediata.")
        _coletar()

    if not horario:
        if run_on_start:
            logger.info("[SchedulerService] COLETA_HORARIO vazio — encerrando após coleta única.")
            return 0
        logger.warning(
            "[SchedulerService] COLETA_HORARIO vazio e RUN_ON_START desligado — nada a agendar. Encerrando."
        )
        return 0

    try:
        hora, minuto = _parse_horario(horario)
    except ValueError:
        logger.error("[SchedulerService] COLETA_HORARIO inválido: %r. Use HH:MM.", horario)
        return 1

    scheduler = BlockingScheduler()
    scheduler.add_job(
        _coletar,
        trigger=CronTrigger(hour=hora, minute=minuto),
        id="coleta_diaria",
        replace_existing=True,
    )
    logger.info("[SchedulerService] Agendado: coleta diária às %02d:%02d. Aguardando...", hora, minuto)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("[SchedulerService] Encerrando.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
