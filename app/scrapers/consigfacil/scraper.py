from __future__ import annotations

from typing import Any

from app.scrapers.base_scraper import BaseScraper


class ConsigFacilScraper(BaseScraper):
    def validate_access(self) -> None:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        url_atual = self.page.url

        if "pagina_consignatario.php" not in url_atual:
            raise RuntimeError(f"Acesso não validado. URL atual: {url_atual}")

    def collect(self) -> list[dict[str, Any]]:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        ultimo_erro = None

        for tentativa in range(3):
            try:
                tabela = self.page.locator("table.table.table-consig-info").first
                tabela.wait_for(state="visible", timeout=10000)

                linhas = tabela.locator("tbody tr")
                quantidade_linhas = linhas.count()

                resultados: list[dict[str, Any]] = []

                for i in range(quantidade_linhas):
                    linha = linhas.nth(i)
                    colunas = linha.locator("td")
                    quantidade_colunas = colunas.count()

                    if quantidade_colunas < 3:
                        continue

                    folha = colunas.nth(0).inner_text().strip()
                    mes_atual = colunas.nth(1).inner_text().strip()
                    data_corte = colunas.nth(2).inner_text().strip()

                    if not folha and not mes_atual and not data_corte:
                        continue

                    resultados.append(
                        {
                            "folha": folha,
                            "mes_atual": mes_atual,
                            "data_corte": data_corte,
                        }
                    )

                return resultados

            except Exception as e:
                ultimo_erro = e
                self.page.wait_for_timeout(2000)

        raise RuntimeError(f"Falha ao coletar dados da tabela de fechamento: {ultimo_erro}")