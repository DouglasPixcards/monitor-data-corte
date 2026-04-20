import os
from dotenv import load_dotenv

load_dotenv()


def get_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


class Settings:
    HEADLESS = get_bool(os.getenv("HEADLESS"), False)
    TIMEOUT_MS = int(os.getenv("TIMEOUT_MS", "30000"))
    CHROME_CHANNEL = os.getenv("CHROME_CHANNEL", "chrome")


settings = Settings()