from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from playwright.sync_api import (
    sync_playwright,
    Playwright,
    Browser,
    BrowserContext,
    Page,
    Error as PlaywrightError,
)

from app.core.settings import settings
from app.auth.base_auth_strategy import BaseAuthStrategy
from app.storage.file_storage import FileStorageRepository

class BaseScraper(ABC):
    def __init__(
        self,
        processadora_config: dict,
        convenio_config: dict,
        auth_strategy: BaseAuthStrategy,
    ) -> None:
        self.processadora_config = processadora_config
        self.convenio_config = convenio_config
        self.auth_strategy = auth_strategy
        self.storage = FileStorageRepository(base_path=settings.STORAGE_PATH)

        self.processadora = self.convenio_config.get(
            "processadora",
            self.processadora_config.get("nome", "desconhecida")
        )

        self.headless = settings.HEADLESS
        self.timeout = settings.TIMEOUT_MS

        self.channel = None
        if self.processadora_config.get("uses_chrome_channel"):
            self.channel = settings.CHROME_CHANNEL

        self.user_data_dir = self.convenio_config.get("user_data_dir")

        self._playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    def get_target_url(self) -> str:
        if self.convenio_config.get("base_url"):
            return self.convenio_config["base_url"]

        template = self.processadora_config.get("url_template")
        slug = self.convenio_config.get("slug")

        if template and slug:
            return template.format(slug=slug)

        raise ValueError("Não foi possível montar a URL do convênio")

    def start(self) -> None:
        self._playwright = sync_playwright().start()

        if self.user_data_dir:
            self.context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                headless=self.headless,
                channel=self.channel,
            )
            pages = self.context.pages
            self.page = pages[0] if pages else self.context.new_page()
        else:
            self.browser = self._playwright.chromium.launch(
                headless=self.headless,
                channel=self.channel,
            )
            self.context = self.browser.new_context()
            self.page = self.context.new_page()

        self.page.set_default_timeout(self.timeout)

    def stop(self) -> None:
        try:
            if self.page is not None and not self.page.is_closed():
                self.page.close()
        except PlaywrightError:
            pass
        finally:
            self.page = None

        try:
            if self.context is not None:
                self.context.close()
        except PlaywrightError:
            pass
        finally:
            self.context = None

        try:
            if self.browser is not None:
                self.browser.close()
        except PlaywrightError:
            pass
        finally:
            self.browser = None

        try:
            if self._playwright is not None:
                self._playwright.stop()
        except PlaywrightError:
            pass
        finally:
            self._playwright = None

    def run(self) -> dict[str, Any]:
        try:
            self.start()
            self.authenticate()
            self.validate_access()
            dados = self.collect()

            return {
                "processadora": self.processadora,
                "convenio": self.convenio_config.get("nome"),
                "status": "ok",
                "dados": dados,
                "erro": None,
            }

        except Exception as e:
            return {
                "processadora": self.processadora,
                "convenio": self.convenio_config.get("nome"),
                "status": "erro",
                "dados": [],
                "erro": str(e),
            }

        finally:
            self.stop()

    def authenticate(self) -> None:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        target_url = self.get_target_url()
        self.auth_strategy.authenticate(self.page, target_url)

    @abstractmethod
    def validate_access(self) -> None:
        pass

    @abstractmethod
    def collect(self) -> list[dict[str, Any]]:
        pass