from unittest.mock import MagicMock, patch

from app.services.healthcheck import pingar


def test_sem_url_e_noop():
    with patch("app.services.healthcheck.requests.get") as get:
        assert pingar(url="") is False
    get.assert_not_called()


def test_ping_sucesso():
    resp = MagicMock(); resp.ok = True
    with patch("app.services.healthcheck.requests.get", return_value=resp) as get:
        assert pingar(url="https://hc.test/uuid") is True
    get.assert_called_once_with("https://hc.test/uuid", timeout=8)


def test_ping_falha_usa_sufixo_fail():
    resp = MagicMock(); resp.ok = True
    with patch("app.services.healthcheck.requests.get", return_value=resp) as get:
        pingar(sucesso=False, url="https://hc.test/uuid/")
    get.assert_called_once_with("https://hc.test/uuid/fail", timeout=8)


def test_erro_de_rede_e_engolido():
    with patch("app.services.healthcheck.requests.get", side_effect=ConnectionError("recusado")):
        assert pingar(url="https://hc.test/uuid") is False


def test_resposta_nao_2xx_retorna_false():
    resp = MagicMock(); resp.ok = False; resp.status_code = 503
    with patch("app.services.healthcheck.requests.get", return_value=resp):
        assert pingar(url="https://hc.test/uuid") is False
