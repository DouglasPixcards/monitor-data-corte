from __future__ import annotations

from typing import Any

from app.scrapers.base_scraper import BaseScraper
from app.auth.strategies.certificate_auth import CertificateAuthStrategy


class ConsigFacilScraper(BaseScraper):
    def __init__(self) -> None:
        super().__init__(
            processadora="consigfacil",
            base_url="https://www.faciltecnologia.com.br/consigfacil/belterra/validar_certificado_cliente.php",
            headless=False,
            channel="chrome",
        )
        self.auth_strategy = CertificateAuthStrategy()

    def authenticate(self) -> None:
        self.auth_strategy.authenticate(self)

    def validate_access(self) -> None:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        url_atual = self.page.url
        conteudo = self.page.locator("body").inner_text()

        print(conteudo)

        if "pagina_consignatario.php" not in url_atual:
            raise RuntimeError(f"Acesso não validado. URL atual: {url_atual}")

        if "Datas de Fechamento" not in conteudo:
            raise RuntimeError("Acesso validado parcialmente, mas bloco esperado não foi encontrado.")

    def collect(self) -> list[dict[str, Any]]:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        texto = self.page.locator("body").inner_text()

        return [{"texto_bruto": texto}]
    

def coletar() -> dict[str, Any]:
    scraper = ConsigFacilScraper()
    return scraper.run()