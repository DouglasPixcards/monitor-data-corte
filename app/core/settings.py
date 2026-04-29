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

    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS: bool = _bool(os.getenv("SMTP_USE_TLS"), True)
    NOTIFICACAO_DESTINATARIOS: list[str] = [
        e.strip()
        for e in os.getenv("NOTIFICACAO_DESTINATARIOS", "").split(",")
        if e.strip()
    ]


settings = Settings()