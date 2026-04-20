from app.auth.base_auth_strategy import BaseAuthStrategy


class CertificateAuthStrategy(BaseAuthStrategy):
    def authenticate(self, page, target_url: str) -> None:
        page.goto(target_url)
        page.wait_for_load_state("networkidle")