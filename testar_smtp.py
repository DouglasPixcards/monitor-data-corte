from app.services.notification.smtp import EmailSMTPNotificador


notificador = EmailSMTPNotificador(
    host="smtp.office365.com",
    port=587,
    user="douglas.celestino@pixcards.com.br",
    password="my_password",
    use_tls=True,
)

notificador.enviar(
    assunto="Teste SMTP - monitor-data-corte",
    destinatarios=["douglas.celestino@pixcards.com.br"],
    corpo_html="""
    <html>
        <body>
            <h2>Teste de envio SMTP</h2>
            <p>Se este e-mail chegou, a configuração SMTP funcionou.</p>
        </body>
    </html>
    """,
)