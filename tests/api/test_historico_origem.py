from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.main import app
from app.core.enums import EventoTipo
from app.core.models import DadoCorte, Evento, Execucao

client = TestClient(app)


def test_historico_convenio_retorna_so_eventos_de_data():
    cfg = {"processadoras": {"consigfacil": {}},
           "convenios": {"belterra": {"processadora": "consigfacil"}}}
    eventos = [
        Evento(id="e1", tipo=EventoTipo.DATA_CORTE_ALTERADA.value, processadora="consigfacil",
               convenio_key="belterra", execucao_id="x", detectado_em="2026-06-01T08:00:00",
               data_corte_anterior="10/05/2026", data_corte_nova="08/05/2026"),
        Evento(id="e2", tipo=EventoTipo.ERRO_COLETA.value, processadora="consigfacil",
               convenio_key="belterra", execucao_id="x", detectado_em="2026-06-02T08:00:00",
               categoria="rede"),
    ]
    repo = MagicMock()
    repo.listar.return_value = eventos
    with patch("app.api.main.load_processadoras_config", return_value=cfg), \
         patch("app.api.main.build_repositories", return_value=(MagicMock(), MagicMock(), repo)):
        resp = client.get("/convenios/belterra/historico")
    assert resp.status_code == 200
    body = resp.json()
    # só o evento de DATA (alterada) — o ERRO_COLETA fica de fora
    assert len(body) == 1
    assert body[0]["data_corte_nova"] == "08/05/2026"
    # o filtro por convênio foi repassado ao repositório
    assert repo.listar.call_args.kwargs.get("convenio_key") == "belterra"


def test_cortes_atuais_expoe_origem_e_confianca_estavel():
    cfg = {"processadoras": {"uruoca": {}},
           "convenios": {"u1": {"processadora": "uruoca", "nome": "Uruoca"}}}
    execucao = Execucao(id="e1", processadora="uruoca", executada_em="2026-06-01T08:00:00",
                        status="ok", total_convenios=1, success_count=1, error_count=0)
    dado = DadoCorte(id="d1", execucao_id="e1", convenio_key="u1", coletado_em="2026-06-01T08:00:00",
                     convenio_nome="Uruoca", data_corte="06/2026", origem="api_estimativa")
    exec_repo = MagicMock(); exec_repo.buscar_ultima_ok.return_value = execucao
    dados_repo = MagicMock(); dados_repo.buscar_por_execucao.return_value = [dado]
    evento_repo = MagicMock(); evento_repo.listar.return_value = []  # 0 mudanças → estável
    with patch("app.services.consulta_service.load_processadoras_config", return_value=cfg), \
         patch("app.services.consulta_service.build_repositories", return_value=(exec_repo, dados_repo, evento_repo)):
        resp = client.get("/cortes/atuais")
    assert resp.status_code == 200
    [row] = resp.json()
    assert row["origem"] == "api_estimativa"
    assert row["confianca"] == "estavel"


def test_cortes_atuais_confianca_instavel_com_muitas_mudancas():
    cfg = {"processadoras": {"consigfacil": {}},
           "convenios": {"belterra": {"processadora": "consigfacil", "nome": "Belterra"}}}
    execucao = Execucao(id="e1", processadora="consigfacil", executada_em="2026-06-01T08:00:00",
                        status="ok", total_convenios=1, success_count=1, error_count=0)
    dado = DadoCorte(id="d1", execucao_id="e1", convenio_key="belterra",
                     coletado_em="2026-06-01T08:00:00", convenio_nome="Belterra",
                     data_corte="10/05/2026", origem="scraper")
    mudancas = [
        Evento(id=f"m{i}", tipo=EventoTipo.DATA_CORTE_ALTERADA.value, processadora="consigfacil",
               convenio_key="belterra", execucao_id="x", detectado_em=f"2026-06-0{i}T08:00:00",
               data_corte_anterior=f"0{i}/05/2026", data_corte_nova=f"1{i}/05/2026")  # o DIA muda
        for i in range(1, 4)  # 3 mudanças de dia → instável
    ]
    exec_repo = MagicMock(); exec_repo.buscar_ultima_ok.return_value = execucao
    dados_repo = MagicMock(); dados_repo.buscar_por_execucao.return_value = [dado]
    evento_repo = MagicMock(); evento_repo.listar.return_value = mudancas
    with patch("app.services.consulta_service.load_processadoras_config", return_value=cfg), \
         patch("app.services.consulta_service.build_repositories", return_value=(exec_repo, dados_repo, evento_repo)):
        resp = client.get("/cortes/atuais")
    [row] = resp.json()
    assert row["confianca"] == "instavel"


def test_cortes_atuais_avanco_de_mes_nao_vira_instavel():
    # 3 mudanças, mas só de MÊS (mesmo dia 10) → progressão normal, NÃO instável.
    cfg = {"processadoras": {"consigfacil": {}},
           "convenios": {"belterra": {"processadora": "consigfacil", "nome": "Belterra"}}}
    execucao = Execucao(id="e1", processadora="consigfacil", executada_em="2026-06-01T08:00:00",
                        status="ok", total_convenios=1, success_count=1, error_count=0)
    dado = DadoCorte(id="d1", execucao_id="e1", convenio_key="belterra",
                     coletado_em="2026-06-01T08:00:00", convenio_nome="Belterra",
                     data_corte="10/07/2026", origem="scraper")
    rolls = [
        Evento(id=f"r{i}", tipo=EventoTipo.DATA_CORTE_ALTERADA.value, processadora="consigfacil",
               convenio_key="belterra", execucao_id="x", detectado_em=f"2026-06-0{i}T08:00:00",
               data_corte_anterior=f"10/0{i + 3}/2026", data_corte_nova=f"10/0{i + 4}/2026")  # só o mês
        for i in range(1, 4)
    ]
    exec_repo = MagicMock(); exec_repo.buscar_ultima_ok.return_value = execucao
    dados_repo = MagicMock(); dados_repo.buscar_por_execucao.return_value = [dado]
    evento_repo = MagicMock(); evento_repo.listar.return_value = rolls
    with patch("app.services.consulta_service.load_processadoras_config", return_value=cfg), \
         patch("app.services.consulta_service.build_repositories", return_value=(exec_repo, dados_repo, evento_repo)):
        resp = client.get("/cortes/atuais")
    [row] = resp.json()
    assert row["confianca"] == "estavel"
