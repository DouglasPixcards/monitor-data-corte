"""
Script manual para testar a configuração SMTP.
Lê as variáveis do .env — não edite este arquivo com valores reais.

Uso:
    python testar_smtp.py
"""
from app.core.settings import settings
from app.services.notification.smtp import EmailSMTPNotificador

if not settings.SMTP_HOST:
    raise SystemExit("SMTP_HOST não configurado no .env")

if not settings.notification_DESTINATARIOS:
    raise SystemExit("notification_DESTINATARIOS não configurado no .env")

notificador = EmailSMTPNotificador(
    host=settings.SMTP_HOST,
    port=settings.SMTP_PORT,
    user=settings.SMTP_USER,
    password=settings.SMTP_PASSWORD,
    use_tls=settings.SMTP_USE_TLS,
)

notificador.enviar(
    assunto="Teste SMTP - monitor-data-corte",
    destinatarios=settings.notification_DESTINATARIOS,
    corpo_html="<html><body><h2>Teste de envio SMTP</h2><p>Se este e-mail chegou, a configuração SMTP funcionou.</p></body></html>",
)

print(f"E-mail enviado para: {settings.notification_DESTINATARIOS}")