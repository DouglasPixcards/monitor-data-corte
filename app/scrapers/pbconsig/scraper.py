"""Scraper para o PBConsig da Paraíba (Keycloak SSO).

O login é feito via Keycloak:
  POST sso.codata.pb.gov.br → redireciona para consignataria.pbconsig.pb.gov.br

Após autenticação bem-sucedida a URL final contém o domínio pbconsig.pb.gov.br.
Convênios: Paraíba.
"""
from __future__ import annotations

import logging
from typing import Any

from app.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

_SUCCESS_URL_FRAGMENT = "pbconsig.pb.gov.br"
_SUCCESS_INDICATORS = [
    "text=Sair",
    "text=Logout",
    "[class*='dashboard']",
    "[class*='home']",
    "nav",
]


class PbconsigScraper(BaseScraper):
    def validate_access(self) -> None:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        current_url = self.page.url
        logger.info("[PBConsig] URL após autenticação: %s", current_url)

        if _SUCCESS_URL_FRAGMENT in current_url:
            logger.info("[PBConsig] Sessão validada por URL: %s", current_url)
            return

        # Verifica indicadores visuais caso o redirect seja diferente
        for selector in _SUCCESS_INDICATORS:
            try:
                loc = self.page.locator(selector)
                if loc.count() > 0:
                    logger.info("[PBConsig] Sessão validada via seletor: %s", selector)
                    return
            except Exception:
                continue

        raise RuntimeError(
            f"[PBConsig] Autenticação não confirmada. URL atual: {current_url}"
        )

    def collect(self) -> list[dict[str, Any]]:
        data_corte = self.convenio_config.get("data_corte_default")
        if not data_corte:
            raise RuntimeError(
                "[PBConsig] Campo 'data_corte_default' não configurado para este convênio."
            )
        logger.info("[PBConsig] data_corte via default configurado: %s", data_corte)
        return [{"folha": "Padrão", "mes_atual": None, "data_corte": data_corte}]
