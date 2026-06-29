"""Scraper para o portal ProConsig (proconsig.com.br). Convênios: Guarulhos.

Validação declarativa (bloco `validacao`) + extração via helpers (label "Fim:" / "Referência:").
"""
from __future__ import annotations

import logging
from typing import Any

from app.scrapers.declarativo import (
    ScraperDeclarativo,
    com_retry,
    texto_apos_separador,
    valor_opcional_apos_separador,
)

logger = logging.getLogger(__name__)


class ProconsigScraper(ScraperDeclarativo):
    def collect(self) -> list[dict[str, Any]]:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        def _extrair() -> list[dict[str, Any]]:
            # Card "Janela de Processamento": Fim = data de corte; Referência = competência.
            data_corte = texto_apos_separador(self.page, 'p:has-text("Fim:")', sep="Fim:")
            mes_atual = valor_opcional_apos_separador(
                self.page, 'p:has-text("Referência:")', sep="Referência:"
            )
            return [{"data_corte": data_corte, "folha": None, "mes_atual": mes_atual}]

        dados = com_retry(self.page, _extrair)
        logger.info("[ProConsig] %r", dados)
        return dados
