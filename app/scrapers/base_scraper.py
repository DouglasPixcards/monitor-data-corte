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


class BaseScraper(ABC):
    def __init__(
        self,
        processadora: str,
        base_url: str,
        headless: bool = False,
        timeout: int = 30000,
        channel: str = "chrome",
        user_data_dir: str | None = None,
    ) -> None:
        self.processadora = processadora
        self.base_url = base_url
        self.headless = headless
        self.timeout = timeout
        self.channel = channel
        self.user_data_dir = user_data_dir

        self._playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    def start(self) -> None:
        self._playwright = sync_playwright().start()

        if self.user_data_dir:
            self.context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                headless=self.headless,
                channel=self.channel,
            )
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
                "status": "ok",
                "dados": dados,
                "erro": None,
            }

        except Exception as e:
            return {
                "processadora": self.processadora,
                "status": "erro",
                "dados": [],
                "erro": str(e),
            }

        finally:
            self.stop()

    @abstractmethod
    def authenticate(self) -> None:
        pass

    @abstractmethod
    def validate_access(self) -> None:
        pass

    @abstractmethod
    def collect(self) -> list[dict[str, Any]]:
        pass