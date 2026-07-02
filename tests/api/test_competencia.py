from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.main import app
from app.core.models import DadoCorte, Execucao

client = TestClient(app)


def test_cortes_atuais_expoe_competencia_com_offset():
    # cotia e ipmdc: MESMO corte 20/07, mas ipmdc tem offset +1 → competência diferente
    cfg = {"processadoras": {"consiglog": {}},
           "convenios": {
               "cotia": {"processadora": "consiglog", "nome": "Cotia"},                         # offset 0
               "ipmdc": {"processadora": "consiglog", "nome": "IPMDC", "competencia_offset": 1},  # offset +1
           }}
    execucao = Execucao(id="e1", processadora="consiglog", executada_em="2026-06-01T08:00:00",
                        status="ok", total_convenios=2, success_count=2, error_count=0)
    d_cotia = DadoCorte(id="d1", execucao_id="e1", convenio_key="cotia", coletado_em="2026-06-01T08:00:00",
                        convenio_nome="Cotia", data_corte="20/07/2026", origem="scraper")
    d_ipmdc = DadoCorte(id="d2", execucao_id="e1", convenio_key="ipmdc", coletado_em="2026-06-01T08:00:00",
                        convenio_nome="IPMDC", data_corte="20/07/2026", origem="scraper")
    exec_repo = MagicMock(); exec_repo.buscar_ultima_ok.return_value = execucao
    dados_repo = MagicMock(); dados_repo.buscar_por_execucao.return_value = [d_cotia, d_ipmdc]
    evento_repo = MagicMock(); evento_repo.listar.return_value = []
    with patch("app.api.main.load_processadoras_config", return_value=cfg), \
         patch("app.api.main.build_repositories", return_value=(exec_repo, dados_repo, evento_repo)):
        resp = client.get("/cortes/atuais")
    assert resp.status_code == 200
    por_conv = {r["convenio_key"]: r["competencia"] for r in resp.json()}
    assert por_conv["cotia"] == "07/2026"   # offset 0 → mês do corte
    assert por_conv["ipmdc"] == "08/2026"   # offset +1 → mês seguinte
