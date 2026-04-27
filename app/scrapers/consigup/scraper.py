from typing import Any

from app.scrapers.base_scraper import BaseScraper
from typing import Any
import re


class ConsigUpScraper(BaseScraper):
    def validate_access(self) -> None:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        self.page.wait_for_url("**/Inicio/Inicio.aspx", timeout=self.timeout)

    def collect(self) -> list[dict[str, Any]]:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        table = self.page.locator("#MainContent_gvAvisos")
        table.wait_for(timeout=self.timeout)

        rows = table.locator("tr")
        total_rows = rows.count()

        dados: list[dict[str, Any]] = []

        for i in range(1, total_rows):  # pula header
            row = rows.nth(i)
            cells = row.locator("td")

            if cells.count() < 2:
                continue

            data_aviso = cells.nth(0).inner_text().strip()
            descricao = cells.nth(1).inner_text().strip()

            match = re.search(r"CORTE\s+DIA\s+(\d{1,2})", descricao, re.IGNORECASE)

            data_corte = None
            if match:
                dia_corte = match.group(1).zfill(2)
                data_corte = dia_corte

            dados.append({
                "folha": None,
                "mes_atual": None,
                "data_corte": data_corte,
                "data_aviso": data_aviso,
                "descricao": descricao,
            })

        return dados