from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_testar_smtp_sem_host_retorna_422():
    with patch("app.api.main.settings") as mock_settings:
        mock_settings.SMTP_HOST = ""
        mock_settings.notification_DESTINATARIOS = ["analista@empresa.com"]
        resp = client.post("/notification/testar")
    assert resp.status_code == 422
    assert "SMTP_HOST" in resp.json()["detail"]


def test_testar_smtp_sem_destinatarios_retorna_422():
    with patch("app.api.main.settings") as mock_settings:
        mock_settings.SMTP_HOST = "smtp.empresa.com"
        mock_settings.notification_DESTINATARIOS = []
        resp = client.post("/notification/testar")
    assert resp.status_code == 422
    assert "notification_DESTINATARIOS" in resp.json()["detail"]


def test_testar_smtp_envia_e_retorna_ok():
    with patch("app.api.main.settings") as mock_settings, \
         patch("app.api.main.EmailSMTPNotificador") as mock_notificador_cls:
        mock_settings.SMTP_HOST = "smtp.empresa.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_USER = "user@empresa.com"
        mock_settings.SMTP_PASSWORD = "senha"
        mock_settings.SMTP_USE_TLS = True
        mock_settings.notification_DESTINATARIOS = ["analista@empresa.com"]
        mock_notificador_cls.return_value.enviar.return_value = None
        resp = client.post("/notification/testar")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert "analista@empresa.com" in resp.json()["destinatarios"]


def test_testar_smtp_falha_de_conexao_retorna_500():
    with patch("app.api.main.settings") as mock_settings, \
         patch("app.api.main.EmailSMTPNotificador") as mock_notificador_cls:
        mock_settings.SMTP_HOST = "smtp.empresa.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_USER = "user@empresa.com"
        mock_settings.SMTP_PASSWORD = "senha"
        mock_settings.SMTP_USE_TLS = True
        mock_settings.notification_DESTINATARIOS = ["analista@empresa.com"]
        mock_notificador_cls.return_value.enviar.side_effect = ConnectionRefusedError("recusado")
        resp = client.post("/notification/testar")
    assert resp.status_code == 500
    assert "teste" in resp.json()["detail"].lower()
