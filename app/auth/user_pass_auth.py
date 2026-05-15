import logging

from playwright.sync_api import Page

from app.auth.base_auth_strategy import BaseAuthStrategy

logger = logging.getLogger(__name__)


class LoginPasswordAuthStrategy(BaseAuthStrategy):
    def __init__(
        self,
        username: str,
        password: str,
        selectors: dict,
    ) -> None:
        self.username = username
        self.password = password
        self.selectors = selectors

    def _get_locator(self, page: Page, selector_config: dict):
        if selector_config["type"] == "role":
            return page.get_by_role(
                selector_config["role"],
                name=selector_config.get("name"),
            )

        if selector_config["type"] == "css":
            # Suporta múltiplos seletores CSS separados por vírgula — usa o primeiro visível
            value = selector_config["value"]
            candidates = [s.strip() for s in value.split(",")]
            if len(candidates) == 1:
                return page.locator(value)
            # Com múltiplos candidatos: retorna o primeiro seletor que existe no DOM
            for candidate in candidates:
                loc = page.locator(candidate)
                if loc.count() > 0:
                    return loc
            # Fallback: retorna o locator do primeiro candidato e deixa o erro aparecer
            return page.locator(candidates[0])

        raise ValueError(f"Tipo de selector inválido: {selector_config}")

    def authenticate(self, page: Page, target_url: str, timeout: int) -> None:
        page.goto(
            target_url,
            wait_until="domcontentloaded",
            timeout=timeout,
        )

        username_field = self._get_locator(page, self.selectors["username"])
        password_field = self._get_locator(page, self.selectors["password"])
        submit_button = self._get_locator(page, self.selectors["submit"])

        username_field.fill(self.username)
        password_field.fill(self.password)

        success = self.selectors.get("success")
        if success:
            submit_button.click()
            self._get_locator(page, success).wait_for(timeout=timeout)
        else:
            # Aguarda navegação antes de wait_for_load_state para evitar
            # "Target page closed" quando o submit causa redirect imediato
            try:
                with page.expect_navigation(wait_until="domcontentloaded", timeout=timeout):
                    submit_button.click()
            except Exception:
                # Se não houve navegação (SPA ou AJAX), ainda tenta networkidle
                pass

            try:
                page.wait_for_load_state("networkidle", timeout=min(timeout, 30000))
            except Exception:
                logger.debug("networkidle timeout — continuando com URL: %s", page.url)
