from unittest.mock import MagicMock, patch

from app.core.enums import EventoTipo
from app.core.models import Evento
from app.services.notification.alerting import disparar, montar_texto, severidade


def _ev(conv, cat, proc="p", sub=None):
    return Evento(id="x", tipo=EventoTipo.ERRO_COLETA, processadora=proc, convenio_key=conv,
                  execucao_id="e", detectado_em="2026-06-28T08:00:00", categoria=cat, subtipo=sub)


def test_severidade_mapeia_categorias():
    # auth_falhou é a categoria de credencial MAIS COMUM — tem que ser crítico (bug da revisão)
    assert severidade("auth_falhou") == "critico"
    assert severidade("credencial_expirada") == "critico"
    assert severidade("portal_mudou") == "critico"
    assert severidade("salto_suspeito") == "atencao"
    assert severidade("valor_invalido") == "atencao"
    assert severidade("rede") is None
    assert severidade(None) is None


def test_persistente_nao_realerta_todo_dia():
    assert montar_texto([_ev("maringa", "auth_falhou", sub="persistente")]) is None


def test_falha_nova_alerta():
    txt = montar_texto([_ev("maringa", "auth_falhou", sub="falha_nova")])
    assert txt is not None and "maringa" in txt


def test_montar_texto_none_sem_acionaveis():
    assert montar_texto([_ev("a", "rede"), _ev("b", "timeout")]) is None


def test_montar_texto_agrupa_por_severidade():
    txt = montar_texto([_ev("maringa", "credencial_expirada"), _ev("cotia", "valor_invalido")])
    assert "CRITICO" in txt and "ATENCAO" in txt
    assert "maringa" in txt and "cotia" in txt


def test_disparar_sem_url_e_noop():
    with patch("app.services.notification.alerting.requests.post") as post:
        assert disparar([_ev("a", "credencial_expirada")], url="") is False
    post.assert_not_called()


def test_disparar_sem_acionaveis_nao_posta():
    with patch("app.services.notification.alerting.requests.post") as post:
        assert disparar([_ev("a", "rede")], url="https://hook.test") is False
    post.assert_not_called()


def test_disparar_posta_payload_slack():
    resp = MagicMock(); resp.ok = True
    with patch("app.services.notification.alerting.requests.post", return_value=resp) as post:
        assert disparar([_ev("maringa", "credencial_expirada")], url="https://hook.test") is True
    args, kwargs = post.call_args
    assert args[0] == "https://hook.test"
    assert "maringa" in kwargs["json"]["text"]


def test_disparar_erro_engolido():
    with patch("app.services.notification.alerting.requests.post", side_effect=ConnectionError("x")):
        assert disparar([_ev("a", "portal_mudou")], url="https://hook.test") is False
