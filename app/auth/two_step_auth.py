"""Estratégia de autenticação em 2 etapas.

Passo 1: preenche username + submit → aguarda redirect/nova página
Passo 2: preenche password + submit → aguarda networkidle

Usado por: ConsigLog (Login.aspx → LoginSegundaEtapa.aspx)
           ConsigNet (username → Continue → password → Log In)
"""
import logging

from playwright.sync_api import Page

from app.auth.base_auth_strategy import BaseAuthStrategy

logger = logging.getLogger(__name__)


class TwoStepAuthStrategy(BaseAuthStrategy):
    def __init__(self, username: str, password: str, selectors: dict) -> None:
        self.username = username
        self.password = password
        self.selectors = selectors

    def _locator(self, page: Page, key: str):
        sel = self.selectors[key]
        if sel["type"] == "css":
            return page.locator(sel["value"])
        if sel["type"] == "role":
            return page.get_by_role(sel["role"], name=sel.get("name"))
        raise ValueError(f"Tipo de seletor inválido: {sel}")

    def authenticate(self, page: Page, target_url: str, timeout: int) -> None:
        page.goto(target_url, wait_until="domcontentloaded", timeout=timeout)

        # Etapa 1: username
        username_field = self._locator(page, "step1_username")
        username_field.wait_for(state="visible", timeout=timeout)
        username_field.fill(self.username)

        submit1 = self._locator(page, "step1_submit")
        submit1.click()

        # Aguarda a segunda tela aparecer (password field)
        password_field = self._locator(page, "step2_password")
        password_field.wait_for(state="visible", timeout=timeout)

        # Etapa 2: password
        password_field.fill(self.password)

        submit2 = self._locator(page, "step2_submit")
        submit2.click()

        page.wait_for_load_state("networkidle", timeout=timeout)
        logger.info("[TwoStepAuth] Autenticação concluída. URL: %s", page.url)
