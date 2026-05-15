"""Scraper para o portal ConSIGI (consigi.com.br).

Tecnologia: JSF/PrimeFaces (.xhtml).
Convênios: Contagem.
"""
from __future__ import annotations

import logging
from typing import Any

from app.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# Seletores candidatos para descoberta dinâmica em portais JSF
_USERNAME_CANDIDATES = [
    "input[id$='inputCpf']",
    "input[id$='inputUsuario']",
    "input[id$='username']",
    "input[name='j_username']",
    "#cpf",
    "#usuario",
    "#username",
    "input[type='text']:visible",
]

_SUBMIT_CANDIDATES = [
    "button[id$='botaoLogin']",
    "button[id$='btnLogin']",
    "input[type='submit']",
    "button[type='submit']",
    "button:has-text('Entrar')",
    "button:has-text('Acessar')",
    "button:has-text('Login')",
]

# Indicadores de sessão autenticada (qualquer um encontrado = sucesso)
_SUCCESS_INDICATORS = [
    "text=Sair",
    "text=Logout",
    "text=Bem-vindo",
    "text=Início",
    "[id*='menuPrincipal']",
    "[id*='navMenu']",
    "[class*='dashboard']",
]

_LOGIN_URL_FRAGMENT = "login.xhtml"


class ConsigiScraper(BaseScraper):
    def validate_access(self) -> None:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        current_url = self.page.url

        if _LOGIN_URL_FRAGMENT in current_url:
            raise RuntimeError(
                f"Autenticação falhou — ainda na tela de login. URL atual: {current_url}"
            )

        # Aguarda algum indicador de sessão ativa
        for selector in _SUCCESS_INDICATORS:
            try:
                loc = self.page.locator(selector)
                if loc.count() > 0:
                    logger.info("[ConSIGI] Sessão validada via seletor: %s", selector)
                    return
            except Exception:
                continue

        logger.warning(
            "[ConSIGI] Nenhum indicador positivo encontrado, mas URL mudou de login.xhtml — considerado sucesso. URL: %s",
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

                logger.info("[ConSIGI] data_corte=%r mes_atual=%r", data_corte, mes_atual)
                return [{"data_corte": data_corte, "folha": None, "mes_atual": mes_atual}]

            except Exception as e:
                ultimo_erro = e
                logger.debug("[ConSIGI] Tentativa %d falhou: %s", tentativa + 1, e)
                self.page.wait_for_timeout(2000)

        raise RuntimeError(f"[ConSIGI] Falha ao extrair data de corte após 3 tentativas: {ultimo_erro}")
