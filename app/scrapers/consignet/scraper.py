"""Scraper para o portal ConsigNet (www1.consignet.com.br).

Convênios: Defensoria, Maringá, Maringá-Prev, Navegantes, Rancharia, Vilhena.

O portal usa o mesmo domínio para todos os convênios. A diferenciação
é feita pelas credenciais (username/password) que determinam o perfil
e o convênio que o usuário vê após login.
"""
from __future__ import annotations

import logging
from typing import Any

from app.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

_LOGIN_URL_FRAGMENT = "/auth/login"
_SUCCESS_URL_FRAGMENTS = ("/auth/context", "/dashboard", "/home")
_SUCCESS_INDICATORS = [
    "text=Sair",
    "text=Logout",
    "text=Sair do Sistema",
    "text=Dashboard",
    "text=Início",
    "[class*='dashboard']",
    "[class*='sidebar']",
    "[routerlink='/dashboard']",
    "app-sidebar",
    "app-header",
]

_FAILURE_INDICATORS = [
    "text=Usuário ou senha inválidos",
    "text=Credenciais inválidas",
    "text=Acesso negado",
    "text=Login ou senha incorretos",
    "[class*='alert-danger']",
    "[class*='error-message']",
]


class ConsignetScraper(BaseScraper):
    def authenticate(self) -> None:
        super().authenticate()
        # Após login bem-sucedido, ConsigNet redireciona para /auth/context via SPA.
        # O networkidle pode disparar antes do redirect JS completar — aguardamos a URL mudar.
        try:
            self.page.wait_for_url("**/auth/context**", timeout=30000)
        except Exception:
            pass

    def validate_access(self) -> None:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        current_url = self.page.url
        logger.info("[ConsigNet] URL após autenticação: %s", current_url)

        # Checa falha explícita primeiro
        for selector in _FAILURE_INDICATORS:
            try:
                loc = self.page.locator(selector)
                if loc.count() > 0:
                    msg = loc.first.inner_text().strip()
                    raise RuntimeError(
                        f"[ConsigNet] Autenticação falhou. Mensagem: {msg!r}"
                    )
            except RuntimeError:
                raise
            except Exception:
                pass

        # Sucesso por URL (ex: /auth/context = seleção de afiliação pós-login)
        if any(frag in current_url for frag in _SUCCESS_URL_FRAGMENTS):
            logger.info("[ConsigNet] Sessão validada por URL: %s", current_url)
            return

        # Ainda na tela de login = falha
        if _LOGIN_URL_FRAGMENT in current_url:
            raise RuntimeError(
                f"[ConsigNet] Autenticação falhou — ainda em /auth/login. URL: {current_url}"
            )

        for selector in _SUCCESS_INDICATORS:
            try:
                loc = self.page.locator(selector)
                if loc.count() > 0:
                    logger.info("[ConsigNet] Sessão validada via seletor: %s", selector)
                    return
            except Exception:
                continue

        logger.warning(
            "[ConsigNet] Saiu de /auth/login — considerado sucesso. URL: %s",
            current_url,
        )

    def collect(self) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "Coleta de dados não implementada para ConsigNet (autenticação only)."
        )
