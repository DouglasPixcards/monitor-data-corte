from app.auth.base_auth_strategy import BaseAuthStrategy


class CertificateAuthStrategy(BaseAuthStrategy):
    def authenticate(self, scraper) -> None:
        page = scraper.page
        target_url = scraper.get_target_url()

        page.goto(target_url, wait_until="domcontentloaded", timeout=scraper.timeout)
        page.wait_for_timeout(3000)