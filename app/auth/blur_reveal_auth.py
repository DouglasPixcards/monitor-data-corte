"""Estratégia de autenticação com revelação de senha via evento blur.

Alguns portais (ex: Fasitec) mantêm o campo de senha oculto até que
o usuário preencha o login e saia do campo (blur), disparando um JS.

Fluxo:
1. Navega para a URL
2. Preenche username
3. Pressiona Tab para disparar o evento blur → revela o campo de senha
4. Aguarda o campo de senha aparecer
5. Preenche senha + clica submit
"""
import logging

from playwright.sync_api import Page

from app.auth.base_auth_strategy import BaseAuthStrategy

logger = logging.getLogger(__name__)


class BlurRevealAuthStrategy(BaseAuthStrategy):
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

        username_field = self._locator(page, "username")
        username_field.wait_for(state="visible", timeout=timeout)
        username_field.fill(self.username)

        # Tab dispara blur → JS revela o campo de senha
        username_field.press("Tab")
        page.wait_for_timeout(1500)

        password_field = self._locator(page, "password")
        password_field.wait_for(state="visible", timeout=timeout)
        password_field.fill(self.password)

        submit = self._locator(page, "submit")
        submit.click()

        page.wait_for_load_state("networkidle", timeout=timeout)
        logger.info("[BlurRevealAuth] Autenticação concluída. URL: %s", page.url)
