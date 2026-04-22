import os
from dotenv import load_dotenv

load_dotenv()


def _get_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


class Settings:
    SAFECONSIG_CEARA_URL = os.getenv("SAFECONSIG_CEARA_URL", "")
    SAFECONSIG_CEARA_USER = os.getenv("SAFECONSIG_CEARA_USER", "")
    SAFECONSIG_CEARA_PASSWORD = os.getenv("SAFECONSIG_CEARA_PASSWORD", "")
    CONSIGFACIL_BELTERRA_URL = os.getenv("CONSIGFACIL_BELTERRA_URL", "")
    CONSIGFACIL_BELTERRA_USER = os.getenv("CONSIGFACIL_BELTERRA_USER", "")
    CONSIGFACIL_BELTERRA_PASSWORD = os.getenv("CONSIGFACIL_BELTERRA_PASSWORD", "")
    HEADLESS = _get_bool(os.getenv("HEADLESS"), True)
    TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", "180000"))


settings = Settings()