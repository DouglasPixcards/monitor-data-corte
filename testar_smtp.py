import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from dotenv import load_dotenv

from app.core.settings import settings

load_dotenv(override=True)

EMAIL_TO = "douglas.celestino@pixcards.com.br"


def criar_email():
    mensagem = MIMEMultipart("alternative")
    mensagem["Subject"] = "Teste SMTP - PixCard"
    mensagem["From"] = settings.SMTP_USER
    mensagem["To"] = EMAIL_TO

    texto = """
Olá,

Este é um teste de envio SMTP usando Office 365.

Se este e-mail chegou, a configuração funcionou.

Atenciosamente,
Sistema PixCard
"""

    html = """
<html>
  <body>
    <h2>Teste SMTP - PixCard</h2>
    <p>Este é um teste de envio SMTP usando Office 365.</p>
    <p><strong>Se este e-mail chegou, a configuração funcionou.</strong></p>
    <hr>
    <p>Sistema PixCard</p>
  </body>
</html>
"""

    mensagem.attach(MIMEText(texto, "plain", "utf-8"))
    mensagem.attach(MIMEText(html, "html", "utf-8"))

    return mensagem


def testar_smtp():
    mensagem = criar_email()

    print("Iniciando teste SMTP...")
    print(f"Servidor: {settings.SMTP_HOST}:{settings.SMTP_PORT}")
    print(f"Usuário: {settings.SMTP_USER}")
    print(f"Destinatário: {EMAIL_TO}")

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
            smtp.set_debuglevel(1)
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.sendmail(settings.SMTP_USER, [EMAIL_TO], mensagem.as_string())
            print("E-mail enviado com sucesso!")

    except smtplib.SMTPAuthenticationError as erro:
        print("Erro de autenticação.")
        print("Possíveis causas: senha errada, SMTP AUTH desabilitado, MFA ou bloqueio no Office 365.")
        print(erro)

    except smtplib.SMTPException as erro:
        print("Erro SMTP.")
        print(erro)

    except Exception as erro:
        print(f"Erro inesperado: {type(erro).__name__}: {erro}")


if __name__ == "__main__":
    testar_smtp()
