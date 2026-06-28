from unittest.mock import MagicMock, patch

from app.core.enums import EventoTipo
from app.core.models import Evento
from app.services.notification.webhook import disparar_mudancas


def _ev_alterada(conv="belterra"):
    return Evento(id="e1", tipo=EventoTipo.DATA_CORTE_ALTERADA, processadora="consigfacil",
                  convenio_key=conv, execucao_id="x", detectado_em="2026-06-28T08:00:00",
                  data_corte_anterior="10/05/2026", data_corte_nova="08/05/2026")


def test_dispara_post_por_mudanca():
    with patch("app.services.notification.webhook.requests.post") as post:
        n = disparar_mudancas([_ev_alterada()], urls=["https://hook.test/a"])
    assert n == 1
    post.assert_called_once()
    args, kwargs = post.call_args
    assert args[0] == "https://hook.test/a"
    assert kwargs["json"]["data_corte_nova"] == "08/05/2026"
    assert kwargs["json"]["convenio_key"] == "belterra"


def test_sem_urls_e_noop():
    with patch("app.services.notification.webhook.requests.post") as post:
        assert disparar_mudancas([_ev_alterada()], urls=[]) == 0
    post.assert_not_called()


def test_ignora_eventos_que_nao_sao_alteracao():
    erro = Evento(id="e2", tipo=EventoTipo.ERRO_COLETA, processadora="consigfacil",
                  convenio_key="x", execucao_id="x", detectado_em="2026-06-28T08:00:00")
    with patch("app.services.notification.webhook.requests.post") as post:
        assert disparar_mudancas([erro], urls=["https://hook.test/a"]) == 0
    post.assert_not_called()


def test_erro_de_post_e_engolido():
    with patch("app.services.notification.webhook.requests.post",
               side_effect=ConnectionError("recusado")) as post:
        n = disparar_mudancas([_ev_alterada()], urls=["https://hook.test/a"])
    assert n == 0  # não propaga; 0 POSTs OK
    post.assert_called_once()


def test_resposta_nao_2xx_nao_conta_como_ok():
    resp = MagicMock(); resp.ok = False; resp.status_code = 500
    with patch("app.services.notification.webhook.requests.post", return_value=resp):
        n = disparar_mudancas([_ev_alterada()], urls=["https://hook.test/a"])
    assert n == 0
