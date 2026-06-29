"""Scraper para o portal ConSIGI (consigi.com.br).

Tecnologia: JSF/PrimeFaces (.xhtml). Convênios: Contagem.
Validação declarativa (bloco `validacao` em processadoras.json) + extração via helpers.
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


class ConsigiScraper(ScraperDeclarativo):
    def collect(self) -> list[dict[str, Any]]:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        def _extrair() -> list[dict[str, Any]]:
            data_corte = texto_apos_separador(self.page, 'li:has-text("Dia de corte:")')
            mes_atual = valor_opcional_apos_separador(
                self.page, 'li:has-text("Última atualização de margem:")'
            )
            return [{"data_corte": data_corte, "folha": None, "mes_atual": mes_atual}]

        # Portal JSF flaky: retenta a extração (substitui o loop 3× do scraper antigo).
        dados = com_retry(self.page, _extrair)
        logger.info("[ConSIGI] %r", dados)
        return dados
