import os
from dotenv import load_dotenv

load_dotenv(override=True)


def get_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


class Settings:
    HEADLESS = get_bool(os.getenv("HEADLESS"), False)
    TIMEOUT_MS = int(os.getenv("TIMEOUT_MS", "180000"))
    CHROME_CHANNEL = os.getenv("CHROME_CHANNEL", "chrome")
    STORAGE_PATH = os.getenv("STORAGE_PATH", "data")


settings = Settings()