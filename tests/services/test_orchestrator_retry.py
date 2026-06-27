"""Retry POR-CONVÊNIO em erros técnicos (transitórios).

Re-coleta só o(s) convênio(s) com erro técnico — não o lote inteiro. Pula um
convênio quando a falha é de credencial (auth_falhou), known_failure ou
fora_janela (erro determinístico, re-tentar não muda nada). Teto
_MAX_RETENTATIVAS_LOTE = 2 rodadas → no máximo 3 coletas por convênio.

O retry só roda no caminho AGENDADO (``coletar(..., retentar_tecnico=True)``,
usado por ``executar_todas`` e pelo runner diário). O caminho on-demand da API
(``executar`` → ``coletar`` sem o flag) faz coleta única para não pendurar a
resposta síncrona do endpoint.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.services.comparador_service import ComparadorService
from app.services.orchestrator import ColetaOrchestrator


def _conv(key, status, erro=None, known_failure=False, nome=None):
    return {
        "convenio_key": key,
        "convenio_nome": nome or key.title(),
        "status": status,
        "records_count": 1 if status == "ok" else 0,
        "erro": erro,
        "known_failure": known_failure,
    }


def _lote(convenios):
    total = len(convenios)
    success = sum(1 for c in convenios if c["status"] == "ok")
    error = total - success
    status = "ok" if error == 0 else ("erro" if success == 0 else "partial_success")
    records = [
        {
            "convenio_key": c["convenio_key"], "convenio_nome": c["convenio_nome"],
            "folha": "F", "mes_atual": "02/2026", "data_corte": "10/05/2026",
        }
        for c in convenios if c["status"] == "ok"
    ]
    return {
        "processadora": "consigfacil", "status": status,
        "total_convenios": total, "success_count": success, "error_count": error,
        "records": records, "convenios": convenios,
    }


@pytest.fixture
def orch():
    execucao_repo = MagicMock()
    dados_repo = MagicMock()
    evento_repo = MagicMock()
    notificador = MagicMock()
    execucao_repo.buscar_ultima_ok.return_value = None
    dados_repo.buscar_por_execucao.return_value = []
    o = ColetaOrchestrator(
        execucao_repo, dados_repo, evento_repo,
        ComparadorService(), notificador, [],
    )
    return o, execucao_repo


def test_lote_ok_nao_retenta(orch):
    o, _ = orch
    mock = MagicMock(return_value=_lote([_conv("a", "ok")]))
    with patch("app.services.orchestrator.executar_coleta_lote", mock):
        o.coletar("consigfacil", retentar_tecnico=True)
    assert mock.call_count == 1


def test_on_demand_default_nao_retenta_mesmo_com_erro_tecnico(orch):
    # Caminho on-demand da API: coletar() SEM retentar_tecnico não retenta nem
    # com erro técnico — evita pendurar a resposta síncrona do endpoint.
    o, _ = orch
    mock = MagicMock(return_value=_lote([_conv("a", "erro", "Timeout 30000ms exceeded")]))
    with patch("app.services.orchestrator.executar_coleta_lote", mock):
        o.coletar("consigfacil")
    assert mock.call_count == 1


def test_retenta_lote_com_erro_tecnico_ate_recuperar(orch):
    o, execucao_repo = orch
    falha = _lote([_conv("tjsp", "erro", "Timeout 30000ms exceeded")])
    ok = _lote([_conv("tjsp", "ok")])
    mock = MagicMock(side_effect=[falha, ok])
    with patch("app.services.orchestrator.executar_coleta_lote", mock):
        o.coletar("consigfacil", retentar_tecnico=True)
    assert mock.call_count == 2  # inicial + 1 retentativa, parou ao recuperar
    execucao = execucao_repo.salvar.call_args[0][0]
    assert execucao.status == "ok"  # usa o resultado da última tentativa


def test_nao_retenta_quando_so_credencial(orch):
    o, _ = orch
    mock = MagicMock(return_value=_lote([
        _conv("a", "erro", "Autenticação falhou — senha inválida"),
    ]))
    with patch("app.services.orchestrator.executar_coleta_lote", mock):
        o.coletar("consigfacil", retentar_tecnico=True)
    assert mock.call_count == 1  # 100% credencial -> sem retry


def test_nao_retenta_known_failure_tecnico(orch):
    o, _ = orch
    mock = MagicMock(return_value=_lote([
        _conv("a", "erro", "Timeout 30000ms exceeded", known_failure=True),
    ]))
    with patch("app.services.orchestrator.executar_coleta_lote", mock):
        o.coletar("consigfacil", retentar_tecnico=True)
    assert mock.call_count == 1  # falha conhecida não é transitória -> sem retry


def test_erro_de_rede_e_tecnico_entao_retenta(orch):
    o, _ = orch
    mock = MagicMock(return_value=_lote([
        _conv("a", "erro", "net::ERR_CONNECTION_REFUSED ao autenticar"),
    ]))
    with patch("app.services.orchestrator.executar_coleta_lote", mock):
        o.coletar("consigfacil", retentar_tecnico=True)
    assert mock.call_count == 3  # rede = técnico, nunca recupera -> bate o teto


def test_respeita_teto_de_retentativas(orch):
    o, _ = orch
    mock = MagicMock(return_value=_lote([_conv("a", "erro", "Timeout 30000ms exceeded")]))
    with patch("app.services.orchestrator.executar_coleta_lote", mock):
        o.coletar("consigfacil", retentar_tecnico=True)
    assert mock.call_count == 3  # 1 inicial + 2 retentativas (teto), nunca mais


def test_lote_misto_recoleta_so_o_tecnico_nao_a_credencial(orch):
    # Lote misto credencial+técnico: re-coleta SÓ o técnico (b); a credencial (a)
    # nunca é re-coletada (paga a antiga dívida V2 de granularidade por-convênio).
    o, _ = orch
    mock = MagicMock(return_value=_lote([
        _conv("a", "erro", "Autenticação falhou"),
        _conv("b", "erro", "Timeout 30000ms exceeded"),
    ]))
    with patch("app.services.orchestrator.executar_coleta_lote", mock):
        o.coletar("consigfacil", retentar_tecnico=True)
    assert mock.call_count == 3  # inicial + 2 re-coletas de b (teto)
    assert [c.kwargs.get("convenio_filter") for c in mock.call_args_list] == [None, "b", "b"]


def test_fora_janela_nao_retenta(orch):
    # fora_janela não é erro técnico → não dispara o retry rápido do lote,
    # mesmo no caminho agendado (retentar_tecnico=True).
    o, _ = orch
    mock = MagicMock(return_value=_lote([
        _conv("muana", "fora_janela", "[ConsigUp] Fora da janela de acesso (seg–sex 08:00–16:45) — coleta pulada nesta rodada."),
    ]))
    with patch("app.services.orchestrator.executar_coleta_lote", mock):
        o.coletar("consigup", retentar_tecnico=True)
    assert mock.call_count == 1


def test_recoleta_so_o_tecnico_que_falhou(orch):
    o, execucao_repo = orch
    inicial = _lote([_conv("a", "ok"), _conv("b", "erro", "Timeout 30000ms exceeded")])
    sub_b_ok = _lote([_conv("b", "ok")])
    mock = MagicMock(side_effect=[inicial, sub_b_ok])
    with patch("app.services.orchestrator.executar_coleta_lote", mock):
        o.coletar("consigfacil", retentar_tecnico=True)
    assert mock.call_count == 2
    assert mock.call_args_list[1].kwargs.get("convenio_filter") == "b"
    execucao = execucao_repo.salvar.call_args[0][0]
    assert execucao.success_count == 2 and execucao.error_count == 0


def test_nao_recoleta_credencial_so_o_tecnico(orch):
    o, _ = orch
    inicial = _lote([_conv("a", "erro", "Autenticação falhou"), _conv("b", "erro", "Timeout 30000ms exceeded")])
    sub_b = _lote([_conv("b", "ok")])
    mock = MagicMock(side_effect=[inicial, sub_b])
    with patch("app.services.orchestrator.executar_coleta_lote", mock):
        o.coletar("consigfacil", retentar_tecnico=True)
    assert [c.kwargs.get("convenio_filter") for c in mock.call_args_list] == [None, "b"]


def test_teto_por_convenio(orch):
    o, _ = orch
    mock = MagicMock(return_value=_lote([_conv("b", "erro", "Timeout 30000ms exceeded")]))
    with patch("app.services.orchestrator.executar_coleta_lote", mock):
        o.coletar("consigfacil", retentar_tecnico=True)
    assert mock.call_count == 3
