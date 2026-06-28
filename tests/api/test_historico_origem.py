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


def test_cortes_atuais_expoe_origem():
    cfg = {"processadoras": {"uruoca": {}},
           "convenios": {"u1": {"processadora": "uruoca", "nome": "Uruoca"}}}
    execucao = Execucao(id="e1", processadora="uruoca", executada_em="2026-06-01T08:00:00",
                        status="ok", total_convenios=1, success_count=1, error_count=0)
    dado = DadoCorte(id="d1", execucao_id="e1", convenio_key="u1", coletado_em="2026-06-01T08:00:00",
                     convenio_nome="Uruoca", data_corte="06/2026", origem="api_estimativa")
    exec_repo = MagicMock()
    exec_repo.buscar_ultima_ok.return_value = execucao
    dados_repo = MagicMock()
    dados_repo.buscar_por_execucao.return_value = [dado]
    with patch("app.api.main.load_processadoras_config", return_value=cfg), \
         patch("app.api.main.build_repositories", return_value=(exec_repo, dados_repo, MagicMock())):
        resp = client.get("/cortes/atuais")
    assert resp.status_code == 200
    [row] = resp.json()
    assert row["origem"] == "api_estimativa"
