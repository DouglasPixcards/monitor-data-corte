from app.auth.base_auth_strategy import BaseAuthStrategy


class CertificateAuthStrategy(BaseAuthStrategy):
    def authenticate(self, page, target_url: str) -> None:
        page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)