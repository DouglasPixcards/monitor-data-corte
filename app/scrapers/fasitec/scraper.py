"""Scraper para o portal Grupo Fasitec / SICON (sicon.grupofasitec.com.br).

Tecnologia: ASP.NET WebForms (.aspx).
Convênios: Pilar.

Fluxo de autenticação (2 etapas via AJAX/postback):
1. Preenche username → força enable do botão Continuar via JS (o JS client-side
   desabilita o botão até receber token reCAPTCHA, mas o server não valida o token).
2. Clica Continuar → ASP.NET postback → campo senha aparece.
3. Preenche senha → clica submit → aguarda redirect.
"""
from __future__ import annotations

import logging
from typing import Any

from app.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

_LOGIN_URL_FRAGMENT = "Login.aspx"
_SUCCESS_INDICATORS = [
    "text=Sair",
    "text=Logout",
    "text=Sair do Sistema",
    "[id*='lnkSair']",
    "[id*='LinkSair']",
    "[id*='MenuPrincipal']",
    "[class*='dashboard']",
]


class FasitecScraper(BaseScraper):
    def authenticate(self) -> None:
        """Sobrescreve o authenticate do BaseScraper para o fluxo especial Fasitec."""
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        selectors = self.processadora_config["selectors"]
        url = self.get_target_url()
        timeout = self.timeout

        self.page.goto(url, wait_until="domcontentloaded", timeout=timeout)

        # Etapa 1: preenche username
        username_field = self.page.locator(selectors["username"]["value"])
        username_field.wait_for(state="visible", timeout=timeout)
        username_field.fill(self.auth_strategy.username)

        # O botão #btnContinuar fica desabilitado aguardando token reCAPTCHA client-side.
        # O server não valida o token — forçamos o enable via JS.
        self.page.evaluate("document.getElementById('btnContinuar').removeAttribute('disabled')")
        self.page.locator("#btnContinuar").click()

        # Etapa 2: campo senha aparece após postback — espera o elemento diretamente
        password_field = self.page.locator(selectors["password"]["value"])
        password_field.wait_for(state="visible", timeout=timeout)
        password_field.fill(self.auth_strategy.password)

        # Submit — aguarda apenas o redirect inicial (domcontentloaded)
        # O wait pelo link de órgão fica exclusivamente em _selecionar_orgao
        submit = self.page.locator(selectors["submit"]["value"])
        try:
            with self.page.expect_navigation(wait_until="domcontentloaded", timeout=30000):
                submit.click()
        except Exception:
            logger.debug("[Fasitec] Navegação após submit não detectada — continuando. URL: %s", self.page.url)

        logger.info("[Fasitec] Autenticação concluída. URL: %s", self.page.url)

    def validate_access(self) -> None:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        current_url = self.page.url
        logger.info("[Fasitec] URL após autenticação: %s", current_url)

        if _LOGIN_URL_FRAGMENT in current_url:
            # Fasitec mantém Login.aspx após login bem-sucedido e exibe a seleção
            # de órgão na mesma página — detectamos isso como sucesso.
            try:
                body_text = self.page.locator("body").inner_text()
                if "Selecione o Órgão" in body_text or "selecione o orgao" in body_text.lower():
                    logger.info("[Fasitec] Sessão validada — tela de seleção de órgão detectada.")
                    return
            except Exception:
                pass

            error_msg = ""
            try:
                body_text = self.page.locator("body").inner_text()
                for keyword in ("perfil", "Inválid", "inválid", "Usuário não encontrado"):
                    if keyword.lower() in body_text.lower():
                        for line in body_text.splitlines():
                            if keyword.lower() in line.lower():
                                error_msg = line.strip()[:200]
                                break
                        break
            except Exception:
                pass
            raise RuntimeError(
                f"[Fasitec] Autenticação falhou — ainda em Login.aspx. "
                f"Detalhe: {error_msg!r}. URL: {current_url}"
            )

        for selector in _SUCCESS_INDICATORS:
            try:
                loc = self.page.locator(selector)
                if loc.count() > 0:
                    logger.info("[Fasitec] Sessão validada via seletor: %s", selector)
                    return
            except Exception:
                continue

        logger.warning(
            "[Fasitec] Saiu de Login.aspx — considerado sucesso. URL: %s",
            current_url,
        )

    def collect(self) -> list[dict[str, Any]]:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        self._selecionar_orgao()
        self._fechar_modais()
        return self._extrair_table_config()

    def _selecionar_orgao(self) -> None:
        orgao_link = self.page.locator("a[id*='imgEntrarNome']").first
        orgao_link.wait_for(state="visible", timeout=60000)
        logger.info("[Fasitec] Selecionando órgão: %s", orgao_link.inner_text().strip())
        orgao_link.click()
        # Substitui wait_for_url + networkidle pelo elemento que será usado na extração
        try:
            self.page.locator("#table_config").first.wait_for(state="attached", timeout=30000)
        except Exception:
            pass
        logger.info("[Fasitec] Navegou para: %s", self.page.url)

    def _fechar_modais(self) -> None:
        for sel in ['button:has-text("Fechar")', '[id*="btnFechar"]', ".modal .close"]:
            try:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    loc.first.click()
                    self.page.wait_for_timeout(500)
                    logger.info("[Fasitec] Modal fechado via: %s", sel)
                    break
            except Exception:
                pass

    def _extrair_table_config(self) -> list[dict[str, Any]]:
        ultimo_erro = None
        for tentativa in range(3):
            try:
                # Há 3 tabelas com id=table_config; filtra pela que contém "Dia de Corte"
                table = self.page.locator("#table_config").filter(has_text="Dia de Corte")
                table.wait_for(state="attached", timeout=15000)

                tbodies = table.locator("tbody")
                header_cells = tbodies.nth(0).locator("tr").first.locator("th")
                value_cells = tbodies.nth(1).locator("tr").first.locator("td")

                n = min(header_cells.count(), value_cells.count())
                raw: dict[str, str] = {}
                for i in range(n):
                    key = header_cells.nth(i).inner_text().strip()
                    val = value_cells.nth(i).inner_text().strip()
                    if key:
                        raw[key] = val

                logger.info("[Fasitec] Dados extraídos: %s", raw)

                return [{
                    "data_corte": raw.get("Dia de Corte"),
                    "folha": None,
                    "mes_atual": None,
                    **{k: v for k, v in raw.items() if k != "Dia de Corte"},
                }]

            except Exception as e:
                ultimo_erro = e
                logger.debug("[Fasitec] Tentativa %d falhou: %s", tentativa + 1, e)
                self._fechar_modais()
                self.page.wait_for_timeout(2000)

        raise RuntimeError(f"[Fasitec] Falha ao extrair table_config após 3 tentativas: {ultimo_erro}")
