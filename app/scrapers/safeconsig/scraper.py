from __future__ import annotations

from typing import Any

from app.scrapers.base_scraper import BaseScraper
from app.auth.base_auth_strategy import BaseAuthStrategy


class SafeConsigScraper(BaseScraper):
    def __init__(
        self,
        processadora_config: dict,
        convenio_config: dict,
        auth_strategy: BaseAuthStrategy,
    ) -> None:
        super().__init__(
            processadora_config=processadora_config,
            convenio_config=convenio_config,
            auth_strategy=auth_strategy,
        )

    def validate_access(self) -> None:
        raise NotImplementedError("SafeConsigScraper ainda não implementado")

    def collect(self) -> list[dict[str, Any]]:
        raise NotImplementedError("SafeConsigScraper ainda não implementado")
