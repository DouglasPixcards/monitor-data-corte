from unittest.mock import MagicMock, patch

import pytest

from app.core.enums import EventoTipo
from app.core.models import DadoCorte, Execucao
from app.services.comparador_service import ComparadorService
from app.services.orchestrator import ColetaOrchestrator
from app.storage.file_storage import (
    FileDadosCorteRepository,
    FileEventoRepository,
    FileExecucaoRepository,
)


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
    "convenios": [
        {"convenio_key": "belterra", "convenio_nome": "Belterra", "status": "ok", "erro": None},
    ],
}

RESULTADO_LOTE_PARCIAL = {
    "processadora": "consigfacil",
    "status": "partial_success",
    "total_convenios": 2,
    "success_count": 1,
    "error_count": 1,
    "records": [
        {
            "convenio_key": "belterra",
            "convenio_nome": "Belterra",
            "folha": "FOLHA 02",
            "mes_atual": "02/2026",
            "data_corte": "10/05/2026",
        }
    ],
    "convenios": [
        {"convenio_key": "belterra", "convenio_nome": "Belterra", "status": "ok", "erro": None},
        {"convenio_key": "tjsp", "convenio_nome": "TJSP", "status": "erro", "erro": "Timeout na página"},
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


def test_primeira_execucao_envia_resumo(orch):
    # Agora o resumo diário é enviado SEMPRE (confirma que a coleta rodou),
    # mesmo na primeira execução sem mudança de ação.
    o, _, _, _, notificador = orch
    with patch("app.services.orchestrator.executar_coleta_lote", return_value=RESULTADO_LOTE_OK):
        execucao = o.executar("consigfacil")
    assert execucao.status == "ok"
    notificador.enviar.assert_called_once()
    assert notificador.enviar.call_args[0][0].startswith("[OK]")


def test_mudanca_dispara_email(orch):
    o, execucao_repo, dados_repo, _, notificador = orch
    execucao_repo.buscar_ultima_ok.return_value = _execucao_ok()
    dados_repo.buscar_por_execucao.return_value = [_dado("12/05/2026")]  # data diferente
    with patch("app.services.orchestrator.executar_coleta_lote", return_value=RESULTADO_LOTE_OK):
        o.executar("consigfacil")
    notificador.enviar.assert_called_once()


def test_sem_mudanca_ainda_envia_resumo_diario(orch):
    o, execucao_repo, dados_repo, _, notificador = orch
    execucao_repo.buscar_ultima_ok.return_value = _execucao_ok()
    dados_repo.buscar_por_execucao.return_value = [_dado("10/05/2026")]  # mesma data
    with patch("app.services.orchestrator.executar_coleta_lote", return_value=RESULTADO_LOTE_OK):
        o.executar("consigfacil")
    # Mesmo sem mudança, o resumo diário sai (consolidado/não-imediato).
    notificador.enviar.assert_called_once()


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


def test_erros_convenio_persistidos_na_execucao(orch):
    o, execucao_repo, _, _, _ = orch
    with patch("app.services.orchestrator.executar_coleta_lote", return_value=RESULTADO_LOTE_PARCIAL):
        o.executar("consigfacil")
    execucao_salva = execucao_repo.salvar.call_args[0][0]
    assert len(execucao_salva.erros) == 1
    assert execucao_salva.erros[0]["convenio_key"] == "tjsp"
    assert execucao_salva.erros[0]["erro"] == "Timeout na página"


def test_execucao_sem_erros_tem_lista_vazia(orch):
    o, execucao_repo, _, _, _ = orch
    with patch("app.services.orchestrator.executar_coleta_lote", return_value=RESULTADO_LOTE_OK):
        o.executar("consigfacil")
    execucao_salva = execucao_repo.salvar.call_args[0][0]
    assert execucao_salva.erros == []


def test_dados_carregados_antes_de_salvar_nova_execucao(orch):
    """Garante que buscar_ultima_ok é chamado antes de salvar a nova execução."""
    o, execucao_repo, dados_repo, _, _ = orch
    call_order = []
    execucao_repo.buscar_ultima_ok.side_effect = lambda p: call_order.append("buscar") or None
    execucao_repo.buscar_ultima.side_effect = lambda p: None
    execucao_repo.salvar.side_effect = lambda e: call_order.append("salvar")
    with patch("app.services.orchestrator.executar_coleta_lote", return_value=RESULTADO_LOTE_OK):
        o.executar("consigfacil")
    assert call_order.index("buscar") < call_order.index("salvar")


# --- Integração com repositórios de arquivo (transição de status real) ---

class _FakeNotificador:
    def __init__(self):
        self.enviados = []

    def enviar(self, assunto, destinatarios, corpo_html):
        self.enviados.append((assunto, destinatarios, corpo_html))


def _lote_belterra(status, erro=None):
    ok = status == "ok"
    return {
        "processadora": "consigfacil", "status": status,
        "total_convenios": 1, "success_count": 1 if ok else 0, "error_count": 0 if ok else 1,
        "records": ([{"convenio_key": "belterra", "convenio_nome": "Belterra",
                      "folha": "FOLHA 02", "mes_atual": "02/2026", "data_corte": "10/05/2026"}] if ok else []),
        "convenios": [{"convenio_key": "belterra", "convenio_nome": "Belterra",
                       "status": status, "records_count": 1 if ok else 0,
                       "erro": erro, "known_failure": False}],
    }


def test_falha_nova_gera_evento_e_email_de_acao(tmp_path):
    base = str(tmp_path)
    notif = _FakeNotificador()

    def _novo_orch():
        return ColetaOrchestrator(
            FileExecucaoRepository(base), FileDadosCorteRepository(base), FileEventoRepository(base),
            ComparadorService(), notif, ["analista@empresa.com"],
        )

    # Rodada 1: belterra coleta ok (cria baseline real em disco).
    with patch("app.services.orchestrator.executar_coleta_lote", return_value=_lote_belterra("ok")):
        _novo_orch().coletar("consigfacil")

    # Rodada 2: belterra falha — inspeciona o bundle (determinístico) e o e-mail.
    notif.enviados.clear()
    with patch("app.services.orchestrator.executar_coleta_lote",
               return_value=_lote_belterra("erro", "[Belterra] Autenticação falhou")):
        orch = _novo_orch()
        bundle = orch.coletar("consigfacil")
        orch.notificar_agregado([bundle])

    erros = [e for e in bundle.eventos if e.tipo == EventoTipo.ERRO_COLETA]
    assert len(erros) == 1
    assert erros[0].subtipo == "falha_nova"
    assert erros[0].categoria == "auth_falhou"
    assert erros[0].detalhe == "[Belterra] Autenticação falhou"
    assert len(notif.enviados) == 1
    assert notif.enviados[0][0].startswith("[Ação]")


def test_executar_todas_envia_um_unico_email_agregado(tmp_path):
    base = str(tmp_path)
    notif = _FakeNotificador()
    orch = ColetaOrchestrator(
        FileExecucaoRepository(base), FileDadosCorteRepository(base), FileEventoRepository(base),
        ComparadorService(), notif, ["analista@empresa.com"],
    )

    def fake_lote(proc, convenio_filter=None):
        ck = f"{proc}_c"
        return {
            "processadora": proc, "status": "ok",
            "total_convenios": 1, "success_count": 1, "error_count": 0,
            "records": [{"convenio_key": ck, "convenio_nome": proc.title(),
                         "folha": "F", "mes_atual": "02/2026", "data_corte": "10/05/2026"}],
            "convenios": [{"convenio_key": ck, "convenio_nome": proc.title(), "status": "ok",
                           "records_count": 1, "erro": None, "known_failure": False}],
        }

    with patch("app.services.orchestrator.executar_coleta_lote", side_effect=fake_lote):
        orch.executar_todas(["consigi", "konexia", "pbconsig"])

    assert len(notif.enviados) == 1  # UM e-mail só pras 3 processadoras
    assunto = notif.enviados[0][0]
    assert "3 processadoras" in assunto
    assert "Coleta diária" in assunto


def test_sem_dado_quando_status_ok_mas_sem_data_de_corte(tmp_path):
    base = str(tmp_path)
    notif = _FakeNotificador()

    def _novo_orch():
        return ColetaOrchestrator(
            FileExecucaoRepository(base), FileDadosCorteRepository(base), FileEventoRepository(base),
            ComparadorService(), notif, ["analista@empresa.com"],
        )

    # Rodada 1: belterra coleta COM data (baseline "coletado").
    with patch("app.services.orchestrator.executar_coleta_lote", return_value=_lote_belterra("ok")):
        _novo_orch().executar("consigfacil")

    # Rodada 2: status ok, mas o registro vem SEM data de corte -> sem_dado.
    lote_vazio = {
        "processadora": "consigfacil", "status": "ok",
        "total_convenios": 1, "success_count": 1, "error_count": 0,
        "records": [{"convenio_key": "belterra", "convenio_nome": "Belterra",
                     "folha": "FOLHA 02", "mes_atual": "02/2026", "data_corte": None}],
        "convenios": [{"convenio_key": "belterra", "convenio_nome": "Belterra", "status": "ok",
                       "records_count": 1, "erro": None, "known_failure": False}],
    }
    with patch("app.services.orchestrator.executar_coleta_lote", return_value=lote_vazio):
        bundle = _novo_orch().coletar("consigfacil")

    sem_dado = [e for e in bundle.eventos if e.categoria == "sem_dado"]
    assert len(sem_dado) == 1
    assert sem_dado[0].subtipo == "falha_nova"
