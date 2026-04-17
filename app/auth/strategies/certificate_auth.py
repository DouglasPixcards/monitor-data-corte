from __future__ import annotations

from app.auth.strategies.base_auth_strategy import BaseAuthStrategy


class CertificateAuthStrategy(BaseAuthStrategy):
    def authenticate(self, scraper) -> None:
        if scraper.page is None:
            raise RuntimeError("Page não inicializada.")

        scraper.page.goto(scraper.base_url, wait_until="networkidle")