from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.scheduler import SchedulerService


def _svc(horario: str = "08:00") -> SchedulerService:
    return SchedulerService(horario=horario, orchestrator_factory=MagicMock())


def _config_duas_processadoras():
    return {"processadoras": {"consigfacil": {}, "safeconsig": {}}}


def _resultado(status):
    r = MagicMock()
    r.execucao.status = status
    return r


def test_iniciar_sem_horario_nao_agenda_jobs():
    with patch("app.services.scheduler.BackgroundScheduler") as mock_cls:
        svc = _svc(horario="")
        svc.iniciar()
    mock_cls.return_value.add_job.assert_not_called()
    mock_cls.return_value.start.assert_not_called()


def test_iniciar_com_horario_invalido_nao_inicia_scheduler():
    with patch("app.services.scheduler.BackgroundScheduler") as mock_cls, \
         patch("app.services.scheduler.load_processadoras_config", return_value=_config_duas_processadoras()):
        svc = _svc(horario="nao-e-horario")
        svc.iniciar()
    mock_cls.return_value.start.assert_not_called()


def test_iniciar_agenda_um_unico_job_diario():
    # Agora é UM job diário consolidado (e-mail único), não um por processadora.
    with patch("app.services.scheduler.BackgroundScheduler") as mock_cls:
        svc = _svc(horario="08:00")
        svc.iniciar()
    mock_scheduler = mock_cls.return_value
    assert mock_scheduler.add_job.call_count == 1
    mock_scheduler.start.assert_called_once()


def test_iniciar_usa_hora_e_minuto_corretos():
    with patch("app.services.scheduler.BackgroundScheduler") as mock_cls, \
         patch("app.services.scheduler.load_processadoras_config", return_value=_config_duas_processadoras()), \
         patch("app.services.scheduler.CronTrigger") as mock_trigger:
        svc = _svc(horario="14:30")
        svc.iniciar()
    mock_trigger.assert_called_with(hour=14, minute=30)


def test_parar_chama_shutdown_quando_rodando():
    with patch("app.services.scheduler.BackgroundScheduler") as mock_cls:
        mock_cls.return_value.running = True
        svc = _svc()
        svc.parar()
    mock_cls.return_value.shutdown.assert_called_once_with(wait=False)


def test_parar_nao_chama_shutdown_se_nao_iniciado():
    with patch("app.services.scheduler.BackgroundScheduler") as mock_cls:
        mock_cls.return_value.running = False
        svc = _svc()
        svc.parar()
    mock_cls.return_value.shutdown.assert_not_called()


def test_executar_todas_chama_orchestrator():
    factory = MagicMock()
    factory.return_value.executar_todas.return_value = [_resultado("ok")]
    svc = SchedulerService(horario="08:00", orchestrator_factory=factory)
    with patch("app.services.scheduler.load_processadoras_config",
               return_value=_config_duas_processadoras()):
        svc._executar_todas()
    factory.return_value.executar_todas.assert_called_once_with(["consigfacil", "safeconsig"])


def test_executar_todas_captura_excecao_sem_propagar():
    factory = MagicMock()
    factory.return_value.executar_todas.side_effect = RuntimeError("scraper quebrou")
    svc = SchedulerService(horario="08:00", orchestrator_factory=factory)
    with patch("app.services.scheduler.load_processadoras_config",
               return_value=_config_duas_processadoras()), \
         patch("app.services.scheduler.healthcheck.pingar") as pingar:
        svc._executar_todas()  # não deve levantar
    pingar.assert_called_once_with(sucesso=False)


def test_executar_todas_pinga_sucesso_quando_alguma_coleta():
    factory = MagicMock()
    factory.return_value.executar_todas.return_value = [_resultado("ok"), _resultado("erro")]
    svc = SchedulerService(horario="08:00", orchestrator_factory=factory)
    with patch("app.services.scheduler.load_processadoras_config",
               return_value=_config_duas_processadoras()), \
         patch("app.services.scheduler.healthcheck.pingar") as pingar:
        svc._executar_todas()
    pingar.assert_called_once_with(sucesso=True)


def test_executar_todas_pinga_fail_quando_coleta_100pct_quebrada():
    # executar_todas NÃO levanta numa coleta toda-erro → o ping precisa ser /fail (bug da revisão)
    factory = MagicMock()
    factory.return_value.executar_todas.return_value = [_resultado("erro"), _resultado("erro")]
    svc = SchedulerService(horario="08:00", orchestrator_factory=factory)
    with patch("app.services.scheduler.load_processadoras_config",
               return_value=_config_duas_processadoras()), \
         patch("app.services.scheduler.healthcheck.pingar") as pingar:
        svc._executar_todas()
    pingar.assert_called_once_with(sucesso=False)
