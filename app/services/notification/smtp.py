from __future__ import annotations

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.services.notification.base import NotificadorBase


class EmailSMTPNotificador(NotificadorBase):
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        use_tls: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._use_tls = use_tls

    def enviar(self, assunto: str, destinatarios: list[str], corpo_html: str) -> None:
        if not destinatarios:
            return
        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"] = self._user
        msg["To"] = ", ".join(destinatarios)
        msg.attach(MIMEText(corpo_html, "html", "utf-8"))

        context = ssl.create_default_context()
        with smtplib.SMTP(self._host, self._port) as smtp:
            if self._use_tls:
                smtp.starttls(context=context)
            smtp.login(self._user, self._password)
            smtp.sendmail(self._user, destinatarios, msg.as_string())
