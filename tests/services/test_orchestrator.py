from unittest.mock import MagicMock, patch

import pytest

from app.core.enums import EventoTipo
from app.core.models import DadoCorte, Execucao
from app.services.comparador_service import ComparadorService
from app.services.orchestrator import ColetaOrchestrator


def _execucao_ok(id: str = "exec-anterior") -> Execucao:
    return Execucao(
        id=id, processadora="consigfacil",
        executada_em="2026-04-28T08:00:00", status="ok",
        total_convenios=1, success_count=1, error_count=0,
    )


def _dado(data_corte: str, execucao_id: str = "exec-anterior") -> DadoCorte:
    return DadoCorte(
        id="d-old", execucao_id=execucao_id, convenio_key="belterra",
        convenio_nome="Belterra", folha="FOLHA 02", mes_atual="02/2026",
        data_corte=data_corte, coletado_em="2026-04-28T08:00:00",
    )


RESULTADO_LOTE_OK = {
    "processadora": "consigfacil",
    "status": "ok",
    "total_convenios": 1,
    "success_count": 1,
    "error_count": 0,
    "records": [
        {
            "convenio_key": "belterra",
            "convenio_nome": "Belterra",
            "folha": "FOLHA 02",
            "mes_atual": "02/2026",
            "data_corte": "10/05/2026",
        }
    ],
}


@pytest.fixture
def orch():
    execucao_repo = MagicMock()
    dados_repo = MagicMock()
    evento_repo = MagicMock()
    notificador = MagicMock()
    execucao_repo.buscar_ultima_ok.return_value = None
    dados_repo.buscar_por_execucao.return_value = []
    return (
        ColetaOrchestrator(
            execucao_repo=execucao_repo,
            dados_repo=dados_repo,
            evento_repo=evento_repo,
            comparador=ComparadorService(),
            notificador=notificador,
            destinatarios=["analista@empresa.com"],
        ),
        execucao_repo,
        dados_repo,
        evento_repo,
        notificador,
    )


def test_primeira_execucao_nao_envia_email(orch):
    o, _, _, _, notificador = orch
    with patch("app.services.orchestrator.executar_coleta_lote", return_value=RESULTADO_LOTE_OK):
        execucao = o.executar("consigfacil")
    assert execucao.status == "ok"
    notificador.enviar.assert_not_called()


def test_mudanca_dispara_email(orch):
    o, execucao_repo, dados_repo, _, notificador = orch
    execucao_repo.buscar_ultima_ok.return_value = _execucao_ok()
    dados_repo.buscar_por_execucao.return_value = [_dado("12/05/2026")]  # data diferente
    with patch("app.services.orchestrator.executar_coleta_lote", return_value=RESULTADO_LOTE_OK):
        o.executar("consigfacil")
    notificador.enviar.assert_called_once()


def test_sem_mudanca_nao_envia_email(orch):
    o, execucao_repo, dados_repo, _, notificador = orch
    execucao_repo.buscar_ultima_ok.return_value = _execucao_ok()
    dados_repo.buscar_por_execucao.return_value = [_dado("10/05/2026")]  # mesma data
    with patch("app.services.orchestrator.executar_coleta_lote", return_value=RESULTADO_LOTE_OK):
        o.executar("consigfacil")
    notificador.enviar.assert_not_called()


def test_falha_email_nao_propaga_excecao(orch):
    o, execucao_repo, dados_repo, _, notificador = orch
    notificador.enviar.side_effect = Exception("SMTP error")
    execucao_repo.buscar_ultima_ok.return_value = _execucao_ok()
    dados_repo.buscar_por_execucao.return_value = [_dado("12/05/2026")]
    with patch("app.services.orchestrator.executar_coleta_lote", return_value=RESULTADO_LOTE_OK):
        execucao = o.executar("consigfacil")  # não deve levantar
    assert execucao is not None


def test_execucao_salva_com_status_correto(orch):
    o, execucao_repo, _, _, _ = orch
    with patch("app.services.orchestrator.executar_coleta_lote", return_value=RESULTADO_LOTE_OK):
        o.executar("consigfacil")
    execucao_repo.salvar.assert_called_once()
    execucao_salva = execucao_repo.salvar.call_args[0][0]
    assert execucao_salva.status == "ok"
    assert execucao_salva.processadora == "consigfacil"


def test_dados_carregados_antes_de_salvar_nova_execucao(orch):
    """Garante que buscar_ultima_ok é chamado antes de salvar a nova execução."""
    o, execucao_repo, dados_repo, _, _ = orch
    call_order = []
    execucao_repo.buscar_ultima_ok.side_effect = lambda p: call_order.append("buscar") or None
    execucao_repo.salvar.side_effect = lambda e: call_order.append("salvar")
    with patch("app.services.orchestrator.executar_coleta_lote", return_value=RESULTADO_LOTE_OK):
        o.executar("consigfacil")
    assert call_order.index("buscar") < call_order.index("salvar")
