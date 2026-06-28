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
        self._verificar_db_pronto()
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

        # Um ÚNICO job diário que roda todas as processadoras e envia um só e-mail.
        self._scheduler.add_job(
            self._executar_todas,
            trigger=CronTrigger(hour=hora, minute=minuto),
            id="coleta_diaria",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info(
            "Scheduler iniciado: coleta diária consolidada às %s (e-mail único)",
            self._horario,
        )

    @staticmethod
    def _verificar_db_pronto() -> None:
        # Fail-fast no startup da API quando Postgres (espelha o runner diário):
        # DB acessível + schema na head, em vez de falhar lazy na 1a query/coleta
        # agendada. Roda no lifespan da API (que chama iniciar()).
        from app.core.settings import settings
        if settings.STORAGE_BACKEND.strip().lower() == "postgres":
            from app.storage import db
            db.assert_ready()

    def parar(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Scheduler encerrado")

    def _executar_todas(self) -> None:
        processadoras = self._descobrir_processadoras()
        logger.info("Job agendado iniciado: %d processadoras (resumo único)", len(processadoras))
        try:
            self._orchestrator_factory().executar_todas(processadoras)
            logger.info("Job agendado de coleta diária concluído")
        except Exception:
            logger.exception("Falha no job agendado de coleta diária")

    def _parse_horario(self) -> tuple[int, int]:
        partes = self._horario.split(":")
        if len(partes) != 2:
            raise ValueError(self._horario)
        hora, minuto = int(partes[0]), int(partes[1])
        if not (0 <= hora <= 23 and 0 <= minuto <= 59):
            raise ValueError(self._horario)
        return hora, minuto

    def _descobrir_processadoras(self) -> list[str]:
        config = load_processadoras_config()
        return list(config["processadoras"].keys())
