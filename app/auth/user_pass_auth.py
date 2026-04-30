from playwright.sync_api import Page

from app.auth.base_auth_strategy import BaseAuthStrategy


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
            return page.locator(selector_config["value"])

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
        submit_button.click()

        success = self.selectors.get("success")
        if success:
            self._get_locator(page, success).wait_for(timeout=timeout)
        else:
            page.wait_for_load_state("networkidle", timeout=timeout)