from unittest.mock import patch

from app.services.coleta_service import executar_coleta_lote


def test_origem_scraper():
    # Processadora de scraper (sem integration_type) → origem "scraper" (oficial).
    cfg = {
        "processadoras": {"consigfacil": {"selectors": {}}},
        "convenios": {"belterra": {"processadora": "consigfacil", "nome": "Belterra",
                                   "credential_env_key": "X"}},
    }
    with patch("app.services.coleta_service.load_processadoras_config", return_value=cfg), \
         patch("app.services.coleta_service.build_auth_strategy"), \
         patch("app.services.coleta_service.build_scraper") as scr:
        scr.return_value.run.return_value = {
            "status": "ok",
            "dados": [{"folha": "F", "mes_atual": "07/2026", "data_corte": "10/07/2026"}],
        }
        lote = executar_coleta_lote("consigfacil")
    assert lote["records"][0]["origem"] == "scraper"


def test_origem_api_estimativa():
    # Processadora API (integration_type="api") → origem "api_estimativa".
    cfg = {
        "processadoras": {"uruoca": {"integration_type": "api"}},
        "convenios": {"u1": {"processadora": "uruoca", "nome": "Uruoca",
                             "credential_env_key": "X"}},
    }
    with patch("app.services.coleta_service.load_processadoras_config", return_value=cfg), \
         patch("app.services.coleta_service._run_api_collector",
               return_value={"status": "ok",
                             "dados": [{"folha": "virada_competencia", "mes_atual": None,
                                        "data_corte": "06/2026"}]}):
        lote = executar_coleta_lote("uruoca")
    assert lote["records"][0]["origem"] == "api_estimativa"
