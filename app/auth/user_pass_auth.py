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

    def _get_locator(self, page, selector_config):
        if selector_config["type"] == "role":
            return page.get_by_role(
                selector_config["role"],
                name=selector_config.get("name")
            )

        if selector_config["type"] == "css":
            return page.locator(selector_config["value"])

        raise ValueError(f"Tipo de selector inválido: {selector_config}")

    def authenticate(self, page, target_url: str) -> None:
        page.goto(target_url, wait_until="domcontentloaded")

        username_field = self._get_locator(page, self.selectors["username"])
        password_field = self._get_locator(page, self.selectors["password"])
        submit_button = self._get_locator(page, self.selectors["submit"])

        username_field.fill(self.username)
        password_field.fill(self.password)
        submit_button.click()

        success = self.selectors.get("success")
        if success:
            self._get_locator(page, success).wait_for()
        else:
            page.wait_for_load_state("networkidle")