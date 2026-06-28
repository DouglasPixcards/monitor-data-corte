from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.main import app
from app.core.settings import settings

client = TestClient(app)


def _basic(user, pwd):
    token = base64.b64encode(f"{user}:{pwd}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _auth_on():
    # patches que ligam a auth (PANEL_PASSWORD setada)
    return (patch.object(settings, "PANEL_PASSWORD", "segredo"),
            patch.object(settings, "PANEL_USER", "admin"))


def test_auth_desabilitada_por_padrao_endpoint_aberto():
    # PANEL_PASSWORD vazio (default) → sem auth, /health responde.
    assert client.get("/health").status_code == 200


def test_sem_credencial_quando_ativada_retorna_401():
    p1, p2 = _auth_on()
    with p1, p2:
        resp = client.get("/convenios")
    assert resp.status_code == 401
    assert "Basic" in resp.headers.get("WWW-Authenticate", "")


def test_credencial_errada_retorna_401():
    p1, p2 = _auth_on()
    with p1, p2:
        resp = client.get("/convenios", headers=_basic("admin", "errada"))
    assert resp.status_code == 401


def test_credencial_certa_passa():
    repos = (MagicMock(), MagicMock(), MagicMock())
    p1, p2 = _auth_on()
    with p1, p2, \
         patch("app.api.main.load_processadoras_config",
               return_value={"processadoras": {}, "convenios": {}}), \
         patch("app.api.main.build_repositories", return_value=repos):
        resp = client.get("/convenios", headers=_basic("admin", "segredo"))
    assert resp.status_code == 200


def test_health_fica_aberto_mesmo_com_auth():
    p1, p2 = _auth_on()
    with p1, p2:
        assert client.get("/health").status_code == 200


def test_usuario_errado_senha_certa_retorna_401():
    # prova que não há early-exit: senha certa mas usuário errado = 401
    p1, p2 = _auth_on()
    with p1, p2:
        resp = client.get("/convenios", headers=_basic("outro", "segredo"))
    assert resp.status_code == 401


def test_credencial_nao_ascii_nao_derruba_500():
    # header com bytes não-ASCII não pode virar TypeError → 500 (era bug)
    p1, p2 = _auth_on()
    with p1, p2:
        token = base64.b64encode("é:x".encode()).decode()
        resp = client.get("/convenios", headers={"Authorization": f"Basic {token}"})
    assert resp.status_code == 401


def test_header_malformado_retorna_401():
    p1, p2 = _auth_on()
    with p1, p2:
        assert client.get("/convenios", headers={"Authorization": "Bearer xyz"}).status_code == 401
        assert client.get("/convenios", headers={"Authorization": "Basic !!nao-base64!!"}).status_code == 401


def test_senha_com_acento_funciona():
    # senha não-ASCII (ex. "senhação") não pode trancar o operador (era 500)
    repos = (MagicMock(), MagicMock(), MagicMock())
    with patch.object(settings, "PANEL_PASSWORD", "senhação"), \
         patch.object(settings, "PANEL_USER", "admin"), \
         patch("app.api.main.load_processadoras_config",
               return_value={"processadoras": {}, "convenios": {}}), \
         patch("app.api.main.build_repositories", return_value=repos):
        resp = client.get("/convenios", headers=_basic("admin", "senhação"))
    assert resp.status_code == 200
