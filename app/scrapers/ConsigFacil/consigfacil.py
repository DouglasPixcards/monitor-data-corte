from __future__ import annotations

from typing import Any

from app.scrapers.base_scraper import BaseScraper
from app.auth.strategies.certificate_auth import CertificateAuthStrategy
import re


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

        if "pagina_consignatario.php" not in url_atual:
            raise RuntimeError(f"Acesso não validado. URL atual: {url_atual}")

        if "Datas de Fechamento" not in conteudo:
            raise RuntimeError("Acesso validado parcialmente, mas bloco esperado não foi encontrado.")

    def collect(self) -> list[dict[str, Any]]:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        texto = self.page.locator("body").inner_text()

        if "Datas de Fechamento" not in texto:
            return []

        trecho = texto.split("Datas de Fechamento", 1)[1]
        linhas = [linha.strip() for linha in trecho.splitlines() if linha.strip()]

        resultados = []

        for linha in linhas:
            if linha == "Folha\tMês atual\tData de fechamento":
                continue
            if linha == "Ver outros meses":
                continue
            if linha == "Algumas novidades para você":
                continue

            partes = [p.strip() for p in linha.split("\t") if p.strip()]

            if len(partes) >= 3:
                convenio = partes[0]
                mes_atual = partes[1]
                data_corte = partes[2]

                resultados.append(
                    {
                        "convenio": convenio,
                        "mes_atual": mes_atual,
                        "data_corte": data_corte,
                    }
                )

        return resultados
    

def coletar() -> dict[str, Any]:
    scraper = ConsigFacilScraper()
    return scraper.run()