"""Auth do módulo de remessas: service (puro) + rotas (service mockado, sem DB)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.core.settings import settings
from app.services import auth_service
from app.storage.remessas_models import UsuarioRow

client = TestClient(app)

_HDR = {"X-Requested-With": "fetch"}


def _user(role="conciliacao", ativo=True):
    return UsuarioRow(id="u1", username="fulano", display_name="Fulano",
                      password_hash="h", role=role, ativo=ativo)


def _remessas_on():
    # REMESSAS_ENABLED é derivado de STORAGE_BACKEND (property) — basta trocar o backend.
    return patch.object(settings, "STORAGE_BACKEND", "postgres")


# ── service (partes puras) ────────────────────────────────────────────────────

def test_hash_e_verificacao_roundtrip():
    h = auth_service.hash_senha("senha-forte-123")
    assert auth_service.verificar_senha("senha-forte-123", h) is True
    assert auth_service.verificar_senha("errada", h) is False


def test_senha_acima_de_72_bytes_rejeitada():
    with pytest.raises(ValueError):
        auth_service.hash_senha("x" * 73)


def test_criar_usuario_role_invalida():
    with pytest.raises(ValueError):
        auth_service.criar_usuario(MagicMock(), "a", "A", "senha-forte", "gerente")


def test_criar_usuario_normaliza_username():
    session = MagicMock()
    u = auth_service.criar_usuario(session, "  FuLaNo ", "Fulano", "senha-forte", "operacoes")
    assert u.username == "fulano"
    session.add.assert_called_once()


# ── /auth/me ──────────────────────────────────────────────────────────────────

def test_me_com_modulo_desabilitado_e_aberto():
    # backend file (default nos testes) → 200 com user null, sem exigir login
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json() == {"user": None, "remessas_enabled": False}


def test_me_habilitado_sem_sessao_401():
    with _remessas_on(), \
         patch("app.services.auth_service.validar_sessao", return_value=None):
        assert client.get("/auth/me").status_code == 401


def test_me_habilitado_com_sessao():
    with _remessas_on(), \
         patch("app.services.auth_service.validar_sessao", return_value=_user()):
        body = client.get("/auth/me").json()
    assert body["remessas_enabled"] is True
    assert body["user"]["username"] == "fulano"
    assert body["user"]["role"] == "conciliacao"


# ── /auth/login ───────────────────────────────────────────────────────────────

def test_login_com_modulo_desabilitado_503():
    resp = client.post("/auth/login", json={"username": "a", "password": "b"})
    assert resp.status_code == 503


def test_login_invalido_401():
    with _remessas_on(), \
         patch("app.services.auth_service.autenticar", return_value=None):
        resp = client.post("/auth/login", json={"username": "a", "password": "errada"})
    assert resp.status_code == 401


def test_login_ok_seta_cookie_httponly():
    with _remessas_on(), \
         patch("app.services.auth_service.autenticar", return_value=_user()), \
         patch("app.services.auth_service.criar_sessao", return_value="tok123"):
        resp = client.post("/auth/login", json={"username": "fulano", "password": "s3nh4-forte"})
    assert resp.status_code == 200
    cookie = resp.headers.get("set-cookie", "")
    assert "sessao=tok123" in cookie and "HttpOnly" in cookie
    assert resp.json()["user"]["username"] == "fulano"


# ── permissões / CSRF ────────────────────────────────────────────────────────

def test_usuarios_exige_admin_403():
    with _remessas_on(), \
         patch("app.services.auth_service.validar_sessao", return_value=_user(role="operacoes")):
        assert client.get("/auth/usuarios").status_code == 403


def test_mutacao_sem_header_x_requested_with_403():
    # POST autenticado mas sem o header do helper fetch → barrado (anti-CSRF)
    with _remessas_on(), \
         patch("app.services.auth_service.validar_sessao", return_value=_user(role="admin")):
        resp = client.post("/auth/usuarios", json={
            "username": "novo", "display_name": "Novo",
            "password": "senha-forte", "role": "operacoes"})
    assert resp.status_code == 403


# ── middleware: sessão vale como alternativa ao Basic ────────────────────────

def test_sessao_valida_passa_pelo_middleware_basic():
    repos = (MagicMock(), MagicMock(), MagicMock())
    with patch.object(settings, "PANEL_PASSWORD", "segredo"), \
         _remessas_on(), \
         patch("app.services.auth_service.validar_sessao", return_value=_user()), \
         patch("app.api.main.load_processadoras_config",
               return_value={"processadoras": {}, "convenios": {}}), \
         patch("app.api.main.build_repositories", return_value=repos):
        resp = client.get("/convenios", cookies={"sessao": "tok"})
    assert resp.status_code == 200


def test_sem_basic_e_sem_sessao_middleware_401():
    with patch.object(settings, "PANEL_PASSWORD", "segredo"):
        assert client.get("/convenios").status_code == 401


def test_auth_login_isento_do_basic():
    # a tela de login não pode disparar o dialog Basic do navegador
    with patch.object(settings, "PANEL_PASSWORD", "segredo"):
        resp = client.post("/auth/login", json={"username": "a", "password": "b"})
    assert resp.status_code != 401 or "WWW-Authenticate" not in resp.headers
