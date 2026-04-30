from app.auth.base_auth_strategy import BaseAuthStrategy
from playwright.sync_api import Page

class CertificateAuthStrategy(BaseAuthStrategy):
    def authenticate(self, page: Page, target_url: str, timeout: int) -> None:
        page.goto(
            target_url,
            wait_until="domcontentloaded",
            timeout=timeout,
        )
        page.wait_for_timeout(3000)