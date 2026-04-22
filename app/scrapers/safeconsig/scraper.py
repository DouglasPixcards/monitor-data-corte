from __future__ import annotations

from typing import Any

from app.config import settings
from app.scrapers.base_scraper import BaseScraper
from app.auth.certificate_auth import CertificateAuthStrategy


class SafeConsigScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            processadora="safeconsig",
            base_url=settings.SAFECONSIG_CEARA_URL,
            headless=False,
            timeout=settings.TIMEOUT_SECONDS,
            channel="chrome",
        )
        self.username = settings.SAFECONSIG_CEARA_USER
        self.password = settings.SAFECONSIG_CEARA_PASSWORD

        self.auth_strategy = CertificateAuthStrategy()

    def authenticate(self) -> None:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        try:
            self.page.goto(self.base_url)
            self.page.get_by_text("CERTIFICADO DIGITAL").click()
        except Exception as e:
            print(e)
            

    def validate_access(self) -> None:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        # url_atual = self.page.url
        # conteudo = self.page.locator("body").inner_text()

        # if "pagina_consignatario.php" not in url_atual:
        #     raise RuntimeError(f"Acesso não validado. URL atual: {url_atual}")

        # if "Datas de Fechamento" not in conteudo:
        #     raise RuntimeError("Acesso validado parcialmente, mas bloco esperado não foi encontrado.")

    def collect(self) -> list[dict[str, Any]]:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        texto = self.page.locator("body").inner_text()

        print(texto)

        # if "Datas de Fechamento" not in texto:
        #     return []

        # trecho = texto.split("Datas de Fechamento", 1)[1]
        # linhas = [linha.strip() for linha in trecho.splitlines() if linha.strip()]

        resultados = []

        # for linha in linhas:
        #     if linha == "Folha\tMês atual\tData de fechamento":
        #         continue
        #     if linha == "Ver outros meses":
        #         continue
        #     if linha == "Algumas novidades para você":
        #         continue

        #     partes = [p.strip() for p in linha.split("\t") if p.strip()]

        #     if len(partes) >= 3:
        #         convenio = partes[0]
        #         mes_atual = partes[1]
        #         data_corte = partes[2]

        #         resultados.append(
        #             {
        #                 "convenio": convenio,
        #                 "mes_atual": mes_atual,
        #                 "data_corte": data_corte,
        #             }
        #         )

        return resultados
    

def coletar() -> dict[str, Any]:
    scraper = SafeConsigScraper()
    return scraper.run()