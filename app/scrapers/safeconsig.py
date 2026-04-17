from __future__ import annotations

from typing import Any

from app.config import settings
from app.scrapers.base_scraper import BaseScraper


class SafeConsigScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            processadora="safeconsig",
            base_url=settings.SAFECONSIG_CEARA_URL,
            headless=False,
            timeout=settings.TIMEOUT_SECONDS * 1000,
            user_data_dir="profiles/safeconsig_ceara",
        )
        self.username = settings.SAFECONSIG_CEARA_USER
        self.password = settings.SAFECONSIG_CEARA_PASSWORD

    def abrir_login(self) -> None:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")
        self.page.goto(self.base_url, wait_until="domcontentloaded")

    def esta_na_tela_login(self) -> bool:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        try:
            campo_usuario = self.page.locator('input[placeholder*="CPF"], input[placeholder*="Usuário"]')
            campo_senha = self.page.locator('input[placeholder*="senha"], input[type="password"]')

            usuario_visivel = campo_usuario.first.is_visible(timeout=2000)
            senha_visivel = campo_senha.first.is_visible(timeout=2000)

            print(f"[SafeConsig] usuario_visivel={usuario_visivel} senha_visivel={senha_visivel}")

            return usuario_visivel or senha_visivel

        except Exception as e:
            print(f"[SafeConsig] erro ao detectar tela de login: {e}")
            return False
        
    def esta_logado(self) -> bool:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        na_tela_login = self.esta_na_tela_login()
        print(f"[SafeConsig] esta_na_tela_login={na_tela_login}")
        return not na_tela_login

    def login_com_usuario_senha(self) -> bool:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        print("[SafeConsig] iniciando login_com_usuario_senha")
        self.debug_estado_pagina("antes do login user/senha")

        try:
            campo_usuario = self.page.locator('input[placeholder*="CPF"], input[placeholder*="Usuário"]').first
            campo_senha = self.page.locator('input[placeholder*="senha"], input[type="password"]').first
            botao_entrar = self.page.get_by_role("button", name="Entrar")

            campo_usuario.click()
            campo_usuario.fill(self.username)
            print("[SafeConsig] usuário preenchido")

            campo_senha.click()
            campo_senha.fill(self.password)
            print("[SafeConsig] senha preenchida")

            try:
                self.page.locator("iframe[src=\"https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/g/turnstile/f/ov2/av0/rch/1j796/0x4AAAAAAB0OsaT0X2H24JBL/auto/fbE/new/flexible?lang=auto\"]").content_frame.locator("body").click()
            except Exception as e:
                print(e)

            self.salvar_print_debug("debug_antes_click_entrar.png")
            input("dsfdfs:")
            botao_entrar.click()
            print("[SafeConsig] cliquei em Entrar")

            self.page.wait_for_timeout(5000)
            self.debug_estado_pagina("apos tentativa user/senha")
            self.salvar_print_debug("debug_apos_login_user_senha.png")
            self.salvar_html_debug("debug_apos_login_user_senha.html")

            logado = self.esta_logado()
            print(f"[SafeConsig] resultado login_com_usuario_senha = {logado}")
            return logado

        except Exception as e:
            print(f"[SafeConsig] erro no login_com_usuario_senha: {e}")
            self.salvar_print_debug("erro_login_user_senha.png")
            self.salvar_html_debug("erro_login_user_senha.html")
            return False

    def login_com_certificado(self) -> bool:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        print("[SafeConsig] iniciando login_com_certificado")

        try:
            self.page.get_by_text("CERTIFICADO DIGITAL").click()
            print("[SafeConsig] cliquei em CERTIFICADO DIGITAL")

            self.page.wait_for_timeout(3000)
            self.debug_estado_pagina("apos clicar certificado")
            self.salvar_print_debug("debug_apos_certificado.png")
            self.salvar_html_debug("debug_apos_certificado.html")

            logado = self.esta_logado()
            print(f"[SafeConsig] resultado login_com_certificado = {logado}")
            return logado

        except Exception as e:
            print(f"[SafeConsig] erro no login_com_certificado: {e}")
            self.salvar_print_debug("erro_login_certificado.png")
            self.salvar_html_debug("erro_login_certificado.html")
            return False

    def login_manual(self) -> bool:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        print("[SafeConsig] aguardando login manual do usuário...")
        input("Faça o login manualmente e pressione ENTER quando terminar...")

        if self.page is None:
            print("[SafeConsig] page ficou None após login manual")
            return False

        self.debug_estado_pagina("apos login manual")
        self.salvar_print_debug("debug_apos_login_manual.png")
        self.salvar_html_debug("debug_apos_login_manual.html")

        try:
            logado = self.esta_logado()
            print(f"[SafeConsig] resultado login_manual = {logado}")
            return logado
        except Exception as e:
            print(f"[SafeConsig] erro ao validar login manual: {e}")
            return False
    
    def garantir_autenticacao(self) -> None:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        self.abrir_login()
        self.debug_estado_pagina("inicio garantir_autenticacao")

        if self.esta_logado():
            print("[SafeConsig] sessão existente válida")
            if self.auth_manager:
                self.auth_manager.register_validation()
            return

        # print("[SafeConsig] tentando user/senha...")
        # if self.login_com_usuario_senha():
        #     print("[SafeConsig] login user/senha funcionou")
        #     self.debug_cookies()
        #     if self.auth_manager:
        #         self.auth_manager.register_login("usuario_senha", self.get_cookies())
        #     return

        # print("[SafeConsig] user/senha falhou. Tentando certificado...")
        if self.login_com_certificado():
            print("[SafeConsig] login com certificado funcionou")
            self.debug_cookies()
            if self.auth_manager:
                self.auth_manager.register_login("certificado", self.get_cookies())
            return

        print("[SafeConsig] certificado falhou. Indo para manual...")
        return
        if self.login_manual():
            print("[SafeConsig] login manual funcionou")
            self.debug_cookies()
            if self.auth_manager:
                self.auth_manager.register_login("manual", self.get_cookies())
            return

        raise RuntimeError("Nenhuma estratégia de autenticação funcionou.")

    def navegar_para_calendario(self) -> None:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")
        pass

    def extrair_dados_calendario(self) -> list[dict[str, Any]]:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        return [
            {
                "convenio": "ceara",
                "competencia": "2026-04",
                "data_corte": "2026-04-21",
                "origem": "scraping_safeconsig"
            }
        ]

    def collect(self) -> list[dict[str, Any]]:
        try:
            self.garantir_autenticacao()
            return self.extrair_dados_calendario()
        except Exception:
            self.salvar_print_debug("erro_collect.png")
            self.salvar_html_debug("erro_collect.html")
            raise


def coletar() -> dict[str, Any]:
    scraper = SafeConsigScraper()
    return scraper.run()