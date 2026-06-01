from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

import requests

from app.integrations.processors.base.config import BaseIntegrationConfig
from app.integrations.processors.base.exceptions import ApiError

logger = logging.getLogger(__name__)


class BaseApiClient(ABC):
    def __init__(self, config: BaseIntegrationConfig) -> None:
        self.config = config
        self._token: str | None = None

    @abstractmethod
    def autenticar(self) -> str:
        """Autentica e armazena o token. Retorna o token."""

    def _request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        timeout: int = 30,
        **kwargs: Any,
    ) -> dict:
        url = self.config.base_url.rstrip("/") + "/" + path.lstrip("/")
        headers = kwargs.pop("headers", {})
        if token and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {token}"

        try:
            response = requests.request( 
                method,
                url,
                headers=headers,
                timeout=timeout,
                **kwargs,
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise ApiError(
                f"HTTP {exc.response.status_code} em {url}: {exc.response.text[:200]}",
                status_code=exc.response.status_code,
            ) from exc
        except requests.RequestException as exc:
            raise ApiError(f"Falha de rede em {url}: {exc}") from exc

        return response.json()
