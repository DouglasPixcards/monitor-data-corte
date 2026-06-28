from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.main import app
from app.core.enums import EventoTipo
from app.core.models import Evento, Execucao

client = TestClient(app)


def test_metricas_endpoint():
    cfg = {"processadoras": {"p": {}},
           "convenios": {"c1": {"processadora": "p", "nome": "C1"}}}
    execs = [Execucao(id="e", processadora="p", executada_em="2026-06-01T08:00:00", status="ok",
                      total_convenios=10, success_count=9, error_count=1)]
    erro = Evento(id="x", tipo=EventoTipo.ERRO_COLETA, processadora="p", convenio_key="c1",
                  execucao_id="e", detectado_em="2026-06-01T08:00:00", categoria="auth_falhou")
    exec_repo = MagicMock(); exec_repo.listar.return_value = execs
    evento_repo = MagicMock(); evento_repo.listar.return_value = [erro]
    with patch("app.api.main.load_processadoras_config", return_value=cfg), \
         patch("app.api.main.build_repositories", return_value=(exec_repo, MagicMock(), evento_repo)):
        resp = client.get("/metricas")
    assert resp.status_code == 200
    body = resp.json()
    assert body["processadoras"][0]["taxa_atual"] == 0.9
    assert body["convenios_com_falha"][0]["convenio_key"] == "c1"
    assert body["convenios_com_falha"][0]["processadora"] == "p"
