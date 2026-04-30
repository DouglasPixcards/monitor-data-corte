from __future__ import annotations

import logging
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.loader import load_processadoras_config

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(
        self,
        horario: str,
        orchestrator_factory: Callable,
    ) -> None:
        self._horario = horario.strip()
        self._orchestrator_factory = orchestrator_factory
        self._scheduler = BackgroundScheduler()

    def iniciar(self) -> None:
        if not self._horario:
            logger.info("COLETA_HORARIO não configurado — agendamento desabilitado")
            return

        try:
            hora, minuto = self._parse_horario()
        except ValueError:
            logger.error(
                "COLETA_HORARIO inválido: '%s'. Use o formato HH:MM.", self._horario
            )
            return

        processadoras = self._descobrir_processadoras()
        for processadora in processadoras:
            self._scheduler.add_job(
                self._executar,
                trigger=CronTrigger(hour=hora, minute=minuto),
                args=[processadora],
                id=f"coleta_{processadora}",
                replace_existing=True,
            )

        self._scheduler.start()
        logger.info(
            "Scheduler iniciado: %d processadora(s) agendada(s) às %s",
            len(processadoras),
            self._horario,
        )

    def parar(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Scheduler encerrado")

    def _executar(self, processadora: str) -> None:
        logger.info("Job agendado iniciado para %s", processadora)
        try:
            self._orchestrator_factory().executar(processadora)
            logger.info("Job agendado concluído para %s", processadora)
        except Exception:
            logger.exception("Falha no job agendado para %s", processadora)

    def _parse_horario(self) -> tuple[int, int]:
        partes = self._horario.split(":")
        if len(partes) != 2:
            raise ValueError(self._horario)
        return int(partes[0]), int(partes[1])

    def _descobrir_processadoras(self) -> list[str]:
        config = load_processadoras_config()
        return list(config["processadoras"].keys())
