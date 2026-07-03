import os

from dotenv import load_dotenv

load_dotenv(override=True)


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


class Settings:
    HEADLESS: bool = _bool(os.getenv("HEADLESS"), False)
    TIMEOUT_MS: int = int(os.getenv("TIMEOUT_MS", "180000"))
    CHROME_CHANNEL: str = os.getenv("CHROME_CHANNEL", "chrome")
    STORAGE_PATH: str = os.getenv("STORAGE_PATH", "data")

    # Backend de persistência: "file" (JSON/JSONL em STORAGE_PATH) ou "postgres".
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "file")
    # Conexão SQLAlchemy quando STORAGE_BACKEND=postgres.
    # Ex: postgresql+psycopg://user:senha@db:5432/monitor
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS: bool = _bool(os.getenv("SMTP_USE_TLS"), True)
    notification_DESTINATARIOS: list[str] = [
        e.strip()
        for e in os.getenv("NOTIFICACAO_DESTINATARIOS", "").split(",")
        if e.strip()
    ]

    # Webhooks de mudança de data de corte (URLs separadas por vírgula). Vazio = desabilitado.
    WEBHOOK_URLS: list[str] = [
        u.strip()
        for u in os.getenv("WEBHOOK_URLS", "").split(",")
        if u.strip()
    ]

    # Agendamento — formato "HH:MM". Vazio = desabilitado.
    COLETA_HORARIO: str = os.getenv("COLETA_HORARIO", "")

    # Auth básica do painel/API (HTTP Basic). PANEL_PASSWORD vazio = auth DESABILITADA
    # (aberto, comportamento atual); setar a senha no .env da VM liga a proteção.
    PANEL_USER: str = os.getenv("PANEL_USER", "admin")
    PANEL_PASSWORD: str = os.getenv("PANEL_PASSWORD", "")

    # Dead-man's switch: URL de um serviço de uptime (ex.: healthchecks.io) pingada ao fim
    # de cada coleta. Se a coleta não rodar, o ping falta e o serviço alerta. Vazio = off.
    HEALTHCHECK_URL: str = os.getenv("HEALTHCHECK_URL", "")

    # Alerta operacional: webhook (ex.: Slack incoming webhook) que recebe alertas acionáveis
    # com severidade ao fim de cada coleta. Vazio = desabilitado.
    ALERT_WEBHOOK_URL: str = os.getenv("ALERT_WEBHOOK_URL", "")

    # ── Módulo de remessas (multiusuário) ─────────────────────────────────────
    # Sessões de login: validade em horas (default 7 dias).
    SESSION_TTL_HORAS: int = int(os.getenv("SESSION_TTL_HORAS", "168"))
    # Cookie Secure (exige HTTPS) — ligar em produção atrás de TLS.
    COOKIE_SECURE: bool = _bool(os.getenv("COOKIE_SECURE"), False)

    @property
    def REMESSAS_ENABLED(self) -> bool:
        """Remessas é Postgres-only (CRUD multiusuário + auditoria transacional)."""
        return self.STORAGE_BACKEND.strip().lower() == "postgres"


settings = Settings()