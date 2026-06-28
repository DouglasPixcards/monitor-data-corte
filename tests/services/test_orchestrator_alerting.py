from unittest.mock import MagicMock, patch

from app.core.enums import EventoTipo
from app.core.models import Evento, Execucao
from app.services.orchestrator import ColetaOrchestrator, ResultadoColeta


def _orch(destinatarios=None):
    return ColetaOrchestrator(
        execucao_repo=MagicMock(), dados_repo=MagicMock(), evento_repo=MagicMock(),
        comparador=MagicMock(), notificador=MagicMock(), destinatarios=destinatarios or [],
    )


def _ev(conv, cat):
    return Evento(id="x", tipo=EventoTipo.ERRO_COLETA, processadora="p", convenio_key=conv,
                  execucao_id="e", detectado_em="2026-06-28T08:00:00", categoria=cat)


def _resultado(proc, eventos):
    ex = Execucao(id="e", processadora=proc, executada_em="2026-06-28T08:00:00", status="erro",
                  total_convenios=1, success_count=0, error_count=1)
    return ResultadoColeta(processadora=proc, execucao=ex, eventos=eventos)


def test_notificar_agregado_dispara_alerta_com_eventos_achatados():
    # alerta deve disparar mesmo SEM destinatário de e-mail, com os eventos de TODAS as processadoras
    orch = _orch(destinatarios=[])
    resultados = [_resultado("p1", [_ev("a", "auth_falhou")]),
                  _resultado("p2", [_ev("b", "portal_mudou")])]
    with patch("app.services.orchestrator.alerting.disparar") as disparar:
        orch.notificar_agregado(resultados)
    disparar.assert_called_once()
    eventos = disparar.call_args[0][0]
    assert {e.convenio_key for e in eventos} == {"a", "b"}
