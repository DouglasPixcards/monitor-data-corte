from __future__ import annotations

import os
from dataclasses import dataclass

from app.integrations.processors.base.config import BaseIntegrationConfig
from app.integrations.processors.base.exceptions import ConfigurationError


@dataclass
class SafeConsigConfig(BaseIntegrationConfig):
    id_convenio: int

    @classmethod
    def from_env(cls, credential_env_key: str) -> SafeConsigConfig:
        base_url_key = f"{credential_env_key}_BASE_URL"
        id_convenio_key = f"{credential_env_key}_ID_CONVENIO"

        base_url = os.environ.get(base_url_key)
        id_convenio_raw = os.environ.get(id_convenio_key)

        missing = [k for k, v in {base_url_key: base_url, id_convenio_key: id_convenio_raw}.items() if not v]
        if missing:
            raise ConfigurationError(
                f"Variáveis de ambiente obrigatórias não encontradas: {', '.join(missing)}"
            )

        try:
            id_convenio = int(id_convenio_raw)
        except ValueError:
            raise ConfigurationError(
                f"{id_convenio_key} deve ser um inteiro, recebi: {id_convenio_raw!r}"
            )

        base = super().from_env(credential_env_key, base_url)
        return cls(base_url=base.base_url, credentials=base.credentials, id_convenio=id_convenio)
