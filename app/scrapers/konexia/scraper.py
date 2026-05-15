"""Scraper para o portal Konexia (konexia-it.com).

Tecnologia: JSF/PrimeFaces (.xhtml) — mesma plataforma do ConSIGI.
Convênios: Planaltina.
"""
from __future__ import annotations

import logging
from typing import Any

from app.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

_SUCCESS_INDICATORS = [
    "text=Sair",
    "text=Logout",
    "text=Bem-vindo",
    "text=Início",
    "[id*='menuPrincipal']",
    "[id*='navMenu']",
    "[class*='dashboard']",
    "[class*='home']",
]

_LOGIN_URL_FRAGMENT = "login.xhtml"


class KonexiaScraper(BaseScraper):
    def validate_access(self) -> None:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        current_url = self.page.url

        if _LOGIN_URL_FRAGMENT in current_url:
            raise RuntimeError(
                f"Autenticação falhou — ainda na tela de login. URL atual: {current_url}"
            )

        for selector in _SUCCESS_INDICATORS:
            try:
                loc = self.page.locator(selector)
                if loc.count() > 0:
                    logger.info("[Konexia] Sessão validada via seletor: %s", selector)
                    return
            except Exception:
                continue

        logger.warning(
            "[Konexia] URL mudou de login.xhtml — considerado sucesso. URL: %s",
            current_url,
        )

    def collect(self) -> list[dict[str, Any]]:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        ultimo_erro = None
        for tentativa in range(3):
            try:
                li_corte = self.page.locator('li:has-text("Dia de corte:")')
                li_corte.wait_for(state="visible", timeout=15000)

                data_corte = li_corte.inner_text().split(":")[-1].strip()

                mes_atual = None
                li_margem = self.page.locator('li:has-text("Última atualização de margem:")')
                if li_margem.count() > 0:
                    mes_atual = li_margem.inner_text().split(":")[-1].strip()

                logger.info("[Konexia] data_corte=%r mes_atual=%r", data_corte, mes_atual)
                return [{"data_corte": data_corte, "folha": None, "mes_atual": mes_atual}]

            except Exception as e:
                ultimo_erro = e
                logger.debug("[Konexia] Tentativa %d falhou: %s", tentativa + 1, e)
                self.page.wait_for_timeout(2000)

        raise RuntimeError(f"[Konexia] Falha ao extrair data de corte após 3 tentativas: {ultimo_erro}")
