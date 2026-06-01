from __future__ import annotations

import os
from dataclasses import dataclass

from app.integrations.processors.base.auth import ApiCredentials
from app.integrations.processors.base.exceptions import ConfigurationError


@dataclass
class BaseIntegrationConfig:
    base_url: str
    credentials: ApiCredentials

    @classmethod
    def from_env(cls, credential_env_key: str, base_url: str) -> BaseIntegrationConfig:
        username_key = f"{credential_env_key}_USERNAME"
        password_key = f"{credential_env_key}_PASSWORD"

        username = os.environ.get(username_key)
        password = os.environ.get(password_key)

        missing = [k for k, v in {username_key: username, password_key: password}.items() if not v]
        if missing:
            raise ConfigurationError(
                f"Variáveis de ambiente obrigatórias não encontradas: {', '.join(missing)}"
            )

        return BaseIntegrationConfig(
            base_url=base_url,
            credentials=ApiCredentials(username=username, password=password),
        )
