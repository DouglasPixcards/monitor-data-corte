"""SafeConsig collector deriva erro_categoria do TIPO da exceção (sem heurística)."""
from unittest.mock import patch

from app.integrations.processors.base.exceptions import AuthenticationError, ApiError
from app.integrations.processors.safeconsig.collector import SafeConsigApiCollector


def _run_com_excecao(exc):
    cc = {"credential_env_key": "X"}
    with patch("app.integrations.processors.safeconsig.collector.SafeConsigConfig.from_env"), \
         patch("app.integrations.processors.safeconsig.collector.SafeConsigClient") as C:
        C.return_value.autenticar.side_effect = exc
        return SafeConsigApiCollector().run("uruoca", cc)


def test_auth_error_vira_auth_falhou():
    r = _run_com_excecao(AuthenticationError("[SafeConsig] negada (HTTP 401)"))
    assert r["status"] == "erro"
    assert r["erro_categoria"] == "auth_falhou"


def test_api_error_de_rede_vira_rede():
    r = _run_com_excecao(ApiError("Falha de rede ao autenticar: timeout"))
    assert r["status"] == "erro"
    assert r["erro_categoria"] == "rede"


def test_api_error_generico_vira_none():
    # ApiError não-rede → None (cai no fallback classificar_erro a jusante).
    r = _run_com_excecao(ApiError("HTTP 500 ao consultar"))
    assert r["status"] == "erro"
    assert r["erro_categoria"] is None
