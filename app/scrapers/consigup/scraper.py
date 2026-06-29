"""Scraper para o portal ConsigUp. Convênios: Muaná.

Validação declarativa (aguarda a URL da landing) + extração da tabela de avisos por regex.
"""
from __future__ import annotations

from typing import Any

from app.scrapers.declarativo import (
    ScraperDeclarativo,
    linhas_de_tabela,
    primeiro_grupo_regex,
)


class ConsigUpScraper(ScraperDeclarativo):
    def collect(self) -> list[dict[str, Any]]:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        dados: list[dict[str, Any]] = []
        linhas = linhas_de_tabela(self.page, "#MainContent_gvAvisos", timeout=self.timeout)
        for celulas in linhas[1:]:  # pula header
            if len(celulas) < 2:
                continue
            data_aviso, descricao = celulas[0], celulas[1]
            dia = primeiro_grupo_regex(descricao, r"CORTE\s+DIA\s+(\d{1,2})")
            dados.append({
                "folha": descricao,
                "mes_atual": data_aviso,
                "data_corte": dia.zfill(2) if dia else None,
            })
        return dados
