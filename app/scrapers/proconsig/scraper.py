"""Scraper para o portal ProConsig (proconsig.com.br).

Convênios: Guarulhos.
"""
from __future__ import annotations

import logging
from typing import Any

from app.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

_LOGIN_URL_FRAGMENTS = ["/login", "login"]
_SUCCESS_URL_EXCLUSIONS = ["/login"]
_SUCCESS_INDICATORS = [
    "text=Sair",
    "text=Logout",
    "text=Dashboard",
    "text=Painel",
    "[class*='dashboard']",
    "[class*='sidebar']",
    "nav[class*='main']",
]


class ProconsigScraper(BaseScraper):
    def validate_access(self) -> None:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        current_url = self.page.url
        logger.info("[ProConsig] URL após autenticação: %s", current_url)

        if all(fragment in current_url for fragment in _SUCCESS_URL_EXCLUSIONS):
            raise RuntimeError(
                f"[ProConsig] Autenticação falhou — ainda em /login. URL: {current_url}"
            )

        for selector in _SUCCESS_INDICATORS:
            try:
                loc = self.page.locator(selector)
                if loc.count() > 0:
                    logger.info("[ProConsig] Sessão validada via seletor: %s", selector)
                    return
            except Exception:
                continue

        logger.warning(
            "[ProConsig] Nenhum indicador visual encontrado, mas saiu do /login. URL: %s",
            current_url,
        )

    def collect(self) -> list[dict[str, Any]]:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        ultimo_erro = None
        for tentativa in range(3):
            try:
                # Card "Janela de Processamento" — Fim = data de corte
                p_fim = self.page.locator('p:has-text("Fim:")')
                p_fim.wait_for(state="visible", timeout=15000)
                data_corte = p_fim.inner_text().split("Fim:")[-1].strip()

                mes_atual = None
                p_ref = self.page.locator('p:has-text("Referência:")')
                if p_ref.count() > 0:
                    mes_atual = p_ref.inner_text().split("Referência:")[-1].strip()

                logger.info("[ProConsig] data_corte=%r mes_atual=%r", data_corte, mes_atual)
                return [{"data_corte": data_corte, "folha": None, "mes_atual": mes_atual}]

            except Exception as e:
                ultimo_erro = e
                logger.debug("[ProConsig] Tentativa %d falhou: %s", tentativa + 1, e)
                self.page.wait_for_timeout(2000)

        raise RuntimeError(f"[ProConsig] Falha ao extrair data de corte após 3 tentativas: {ultimo_erro}")
