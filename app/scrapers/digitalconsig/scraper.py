"""Scraper para o portal DigitalConsig (sistema.digitalconsig.com.br).

Convênios: Várzea Grande, Vera.
"""
from __future__ import annotations

import logging
from typing import Any

from app.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

_SUCCESS_URL_FRAGMENTS = ("LoginSelecao.aspx", "Home", "Dashboard", "Default")
_SUCCESS_INDICATORS = [
    "text=Sair",
    "text=Logout",
    "text=Dashboard",
    "text=Início",
    "text=Bem-Vindo",
    "text=Selecione o Órgão",
    "[class*='dashboard']",
    "[class*='sidebar']",
    "nav",
]

_FAILURE_INDICATORS = [
    "text=Usuário ou senha inválidos",
    "text=Credenciais inválidas",
    "text=Acesso negado",
    "[class*='error']",
    "[class*='alert-danger']",
]


class DigitalconsigScraper(BaseScraper):
    def validate_access(self) -> None:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        current_url = self.page.url
        logger.info("[DigitalConsig] URL após autenticação: %s", current_url)

        # Verificação positiva por URL (mais confiável)
        if any(fragment in current_url for fragment in _SUCCESS_URL_FRAGMENTS):
            logger.info("[DigitalConsig] Sessão validada por URL: %s", current_url)
            return

        # Detecta falha explícita antes de declarar sucesso
        for selector in _FAILURE_INDICATORS:
            try:
                loc = self.page.locator(selector)
                if loc.count() > 0:
                    msg = loc.first.inner_text().strip()
                    raise RuntimeError(
                        f"[DigitalConsig] Autenticação falhou. Mensagem: {msg!r}"
                    )
            except RuntimeError:
                raise
            except Exception:
                pass

        for selector in _SUCCESS_INDICATORS:
            try:
                loc = self.page.locator(selector)
                if loc.count() > 0:
                    logger.info("[DigitalConsig] Sessão validada via seletor: %s", selector)
                    return
            except Exception:
                continue

        logger.warning(
            "[DigitalConsig] Nenhum indicador visual claro — considerado sucesso pois não há erro. URL: %s",
            current_url,
        )

    def collect(self) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "Coleta de dados não implementada para DigitalConsig (autenticação only)."
        )
