from unittest.mock import patch
from app.services.coleta_service import executar_coleta_lote

_CFG = {
    "processadoras": {"consigup": {"auth_type": "login_password", "selectors": {}}},
    "convenios": {"muana": {"processadora": "consigup", "nome": "PREF DE MUANA - PA",
                            "credential_env_key": "CONSIGUP_MUANA"}},
}


def _patches():
    return (
        patch("app.services.coleta_service.load_processadoras_config", return_value=_CFG),
        patch("app.services.coleta_service.build_auth_strategy"),
        patch("app.services.coleta_service.build_scraper"),
        patch("app.services.coleta_service.dentro_da_janela_consigup"),
    )


def test_fora_da_janela_pula_sem_tocar_portal():
    p_cfg, p_auth, p_scr, p_jan = _patches()
    with p_cfg, p_auth as auth, p_scr as scr, p_jan as jan:
        jan.return_value = False
        lote = executar_coleta_lote("consigup")
    conv = lote["convenios"][0]
    assert conv["status"] == "fora_janela"
    assert lote["status"] == "fora_janela"
    assert lote["error_count"] == 0
    assert lote["fora_janela_count"] == 1
    assert lote["success_count"] == 0
    auth.assert_not_called()   # não construiu credencial
    scr.assert_not_called()    # não tocou o portal


def test_dentro_da_janela_coleta_normal():
    p_cfg, p_auth, p_scr, p_jan = _patches()
    with p_cfg, p_auth, p_scr as scr, p_jan as jan:
        jan.return_value = True
        scr.return_value.run.return_value = {
            "status": "ok",
            "dados": [{"folha": "F", "mes_atual": "07/2026", "data_corte": "10/07/2026"}],
        }
        lote = executar_coleta_lote("consigup")
    assert lote["convenios"][0]["status"] == "ok"
    assert lote["fora_janela_count"] == 0
    scr.return_value.run.assert_called_once()


def test_outra_processadora_nao_pula_fora_da_janela():
    # A regra de janela é só do consigup: outra processadora coleta normalmente
    # mesmo com dentro_da_janela_consigup() False.
    cfg = {
        "processadoras": {"consigfacil": {"auth_type": "certificate", "selectors": {}}},
        "convenios": {"belterra": {"processadora": "consigfacil", "nome": "Belterra",
                                  "credential_env_key": "X"}},
    }
    with patch("app.services.coleta_service.load_processadoras_config", return_value=cfg), \
         patch("app.services.coleta_service.build_auth_strategy"), \
         patch("app.services.coleta_service.build_scraper") as scr, \
         patch("app.services.coleta_service.dentro_da_janela_consigup", return_value=False):
        scr.return_value.run.return_value = {"status": "ok", "dados": []}
        lote = executar_coleta_lote("consigfacil")
    assert lote["convenios"][0]["status"] == "ok"
    assert lote["fora_janela_count"] == 0
    scr.return_value.run.assert_called_once()
