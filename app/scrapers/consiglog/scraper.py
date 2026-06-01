"""Scraper para o portal ConsigLog / SAEC (saec.consiglog.com.br).

Tecnologia: ASP.NET WebForms (.aspx).
Convênios: Cotia-SP, Duque de Caxias-RJ.
"""
from __future__ import annotations

import logging
from typing import Any

from app.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

_LOGIN_URL_FRAGMENTS = ("Login.aspx", "LoginSegundaEtapa.aspx")
_SUCCESS_INDICATORS = [
    "text=Sair",
    "text=Logout",
    "text=Sair do Sistema",
    "[id*='MenuPrincipal']",
    "[id*='menuPrincipal']",
    "[id*='lnkSair']",
    "[class*='dashboard']",
]


class ConsiglogScraper(BaseScraper):
    def authenticate(self) -> None:
        super().authenticate()
        # ConsigLog exibe popup "Usuário já logado" quando há sessão aberta em outro terminal.
        # Confirma o desconectar para prosseguir.
        try:
            confirm_btn = self.page.locator("#ucAjaxModalPopupConfirmacao1_btnConfirmarPopup")
            if confirm_btn.is_visible(timeout=3000):
                logger.info("[ConsigLog] Sessão anterior detectada — confirmando desconexão...")
                try:
                    with self.page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                        confirm_btn.click()
                except Exception:
                    pass
                try:
                    self.page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                logger.info("[ConsigLog] Desconexão confirmada. URL: %s", self.page.url)
        except Exception:
            pass

    def validate_access(self) -> None:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        current_url = self.page.url
        logger.info("[ConsigLog] URL após autenticação: %s", current_url)

        if any(fragment in current_url for fragment in _LOGIN_URL_FRAGMENTS):
            # Verifica mensagem de erro na tela
            error_msg = ""
            for error_sel in ["[id*='lblErro']", "[class*='error']", "[class*='alert']", "body"]:
                try:
                    loc = self.page.locator(error_sel)
                    if loc.count() > 0:
                        text = loc.first.inner_text().strip()
                        if any(kw in text for kw in ("nválid", "Inválid", "tativa")):
                            error_msg = text[:200]
                            break
                except Exception:
                    pass
            raise RuntimeError(
                f"[ConsigLog] Autenticação falhou — ainda em página de login. "
                f"Mensagem: {error_msg!r}. URL: {current_url}"
            )

        for selector in _SUCCESS_INDICATORS:
            try:
                loc = self.page.locator(selector)
                if loc.count() > 0:
                    logger.info("[ConsigLog] Sessão validada via seletor: %s", selector)
                    return
            except Exception:
                continue

        logger.warning(
            "[ConsigLog] Saiu de Login.aspx — considerado sucesso. URL: %s",
            current_url,
        )

    def collect(self) -> list[dict[str, Any]]:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        self._selecionar_orgao()
        return self._extrair_prazos()

    def _selecionar_orgao(self) -> None:
        tabela = self.page.locator("table#gvOrgao")
        tabela.wait_for(state="visible", timeout=self.timeout)

        orgao_sigla = self.convenio_config.get("orgao_sigla")
        if orgao_sigla:
            linha = tabela.locator("tr").filter(has_text=orgao_sigla)
            btn = linha.locator("input[type='image']")
        else:
            btn = tabela.locator("input[type='image']").first

        btn.wait_for(state="visible", timeout=10000)
        logger.info("[ConsigLog] Selecionando órgão: sigla=%r", orgao_sigla)

        try:
            with self.page.expect_navigation(wait_until="domcontentloaded", timeout=30000):
                btn.click()
        except Exception:
            pass
        try:
            self.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        logger.info("[ConsigLog] Navegou para: %s", self.page.url)

    def _extrair_prazos(self) -> list[dict[str, Any]]:
        ultimo_erro = None
        for tentativa in range(3):
            try:
                tabela = self.page.locator("#body_Prazos_gvPrazos")
                tabela.wait_for(state="visible", timeout=20000)

                linhas = tabela.locator("tbody tr")
                resultados: list[dict[str, Any]] = []

                for i in range(linhas.count()):
                    tds = linhas.nth(i).locator("td")
                    if tds.count() < 6:
                        continue

                    servico          = tds.nth(0).inner_text().strip()
                    data_inicio      = tds.nth(3).inner_text().strip()
                    data_final_corte = tds.nth(4).inner_text().strip()
                    folha            = tds.nth(5).inner_text().strip()

                    if not data_final_corte:
                        continue

                    resultados.append({
                        "servico": servico,
                        "data_corte": data_final_corte,
                        "folha": folha,
                        "mes_atual": folha,
                        "data_inicio_corte": data_inicio,
                    })

                logger.info("[ConsigLog] %d linha(s) extraída(s)", len(resultados))
                return resultados

            except Exception as e:
                ultimo_erro = e
                logger.debug("[ConsigLog] Tentativa %d falhou: %s", tentativa + 1, e)
                self.page.wait_for_timeout(2000)

        raise RuntimeError(f"[ConsigLog] Falha ao extrair tabela de prazos após 3 tentativas: {ultimo_erro}")
