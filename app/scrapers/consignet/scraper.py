"""Scraper para o portal ConsigNet (www1.consignet.com.br).

Convênios: Defensoria, Maringá, Maringá-Prev, Navegantes, Rancharia, Vilhena.

A tela /auth/context usa React Virtualized — apenas itens visíveis existem no DOM.
Por isso usamos o campo #context-search para filtrar antes de clicar.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from app.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

_URL_CONTEXT        = "https://www.www1.consignet.com.br/auth/context"
_LOGIN_URL_FRAGMENT = "/auth/login"
_SUCCESS_URL_FRAGMENTS = ("/auth/context", "/dashboard", "/home")

_FAILURE_INDICATORS = [
    "text=Usuário ou senha inválidos",
    "text=Credenciais inválidas",
    "text=Acesso negado",
    "text=Login ou senha incorretos",
    "[class*='alert-danger']",
    "[class*='error-message']",
]

_CONTEXT_ITEM      = ".context-item"
_SEARCH_INPUT      = "#context-search"

_CLICK_TIMEOUT_MS  = 10_000
_NAV_TIMEOUT_MS    = 30_000
_LOAD_TIMEOUT_MS   = 20_000
_CUTOFF_TIMEOUT_MS = 15_000
_SEARCH_DEBOUNCE_MS = 700


class ConsignetScraper(BaseScraper):
    def authenticate(self) -> None:
        super().authenticate()
        try:
            self.page.wait_for_url("**/auth/context**", timeout=30000)
        except Exception:
            pass

    def validate_access(self) -> None:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        current_url = self.page.url
        logger.info("[ConsigNet] URL após autenticação: %s", current_url)

        for selector in _FAILURE_INDICATORS:
            try:
                loc = self.page.locator(selector)
                if loc.count() > 0:
                    msg = loc.first.inner_text().strip()
                    raise RuntimeError(f"[ConsigNet] Autenticação falhou. Mensagem: {msg!r}")
            except RuntimeError:
                raise
            except Exception:
                pass

        if any(frag in current_url for frag in _SUCCESS_URL_FRAGMENTS):
            logger.info("[ConsigNet] Sessão validada por URL: %s", current_url)
            return

        if _LOGIN_URL_FRAGMENT in current_url:
            raise RuntimeError(
                f"[ConsigNet] Autenticação falhou — ainda em /auth/login. URL: {current_url}"
            )

        logger.warning("[ConsigNet] Saiu de /auth/login — considerado sucesso. URL: %s", current_url)

    # ------------------------------------------------------------------
    # Coleta
    # ------------------------------------------------------------------

    def collect(self) -> list[dict[str, Any]]:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        afiliacao = self.convenio_config.get("afiliacao")
        if not afiliacao:
            raise RuntimeError("[ConsigNet] Campo 'afiliacao' não configurado para este convênio.")

        return self._coletar_afiliacao(afiliacao)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _garantir_tela_context(self) -> None:
        if "/auth/context" not in self.page.url:
            self.page.goto(_URL_CONTEXT, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
        try:
            self.page.wait_for_selector(_SEARCH_INPUT, state="visible", timeout=10_000)
        except Exception:
            pass
        # Limpa busca anterior para não herdar filtro de iteração anterior
        try:
            search = self.page.locator(_SEARCH_INPUT)
            if search.is_visible():
                search.fill("")
        except Exception:
            pass

    def _coletar_afiliacao(self, nome: str) -> list[dict[str, Any]]:
        self._garantir_tela_context()

        # A lista usa React Virtualized — só renderiza itens visíveis.
        # Digita no campo de busca para forçar o item aparecer no DOM.
        search = self.page.locator(_SEARCH_INPUT)
        search.wait_for(state="visible", timeout=10_000)
        search.fill(nome)
        self.page.wait_for_timeout(_SEARCH_DEBOUNCE_MS)

        item = self.page.locator(_CONTEXT_ITEM).first
        item.wait_for(state="visible", timeout=_CUTOFF_TIMEOUT_MS)

        texto_encontrado = item.inner_text().strip()
        logger.info("[ConsigNet] Clicando: %r (buscado: %r)", texto_encontrado, nome)

        dashboard_page = self._clicar_e_obter_pagina_dashboard(item)
        data_corte = self._extrair_cutoff_date(dashboard_page)
        logger.info("[ConsigNet] %s → data_corte=%r", nome, data_corte)

        if dashboard_page is not self.page:
            try:
                dashboard_page.close()
            except Exception:
                pass

        return [{"folha": texto_encontrado, "mes_atual": None, "data_corte": data_corte}]

    def _clicar_e_obter_pagina_dashboard(self, item_locator) -> Any:
        """Clica num item de afiliação e retorna a página do dashboard.

        Trata dois cenários:
        - Portal abre nova janela  → retorna a nova Page
        - Portal navega na mesma janela → retorna self.page
        """
        ids_antes = {id(p) for p in self.context.pages}

        try:
            item_locator.click(timeout=_CLICK_TIMEOUT_MS)
        except Exception as e:
            logger.debug("[ConsigNet] click exception: %s", e)

        time.sleep(3)

        novas = [p for p in self.context.pages if id(p) not in ids_antes]

        if novas:
            dashboard_page = novas[0]
            logger.info("[ConsigNet] Nova janela — URL: %s", dashboard_page.url)
            try:
                dashboard_page.wait_for_load_state("domcontentloaded", timeout=_NAV_TIMEOUT_MS)
            except Exception:
                pass
            try:
                dashboard_page.wait_for_load_state("networkidle", timeout=_LOAD_TIMEOUT_MS)
            except Exception:
                pass
            return dashboard_page

        logger.info("[ConsigNet] Mesma janela — URL: %s", self.page.url)
        try:
            self.page.wait_for_url(
                lambda url: "/auth/context" not in url,
                timeout=_NAV_TIMEOUT_MS,
            )
        except Exception:
            pass
        try:
            self.page.wait_for_load_state("networkidle", timeout=_LOAD_TIMEOUT_MS)
        except Exception:
            pass
        return self.page

    def _extrair_cutoff_date(self, page) -> str | None:
        """Extrai o valor do card 'Cut-off Date' no dashboard.

        Sobe pelo DOM a partir do h6 'Cut-off Date' até encontrar um pai que
        contenha um h3 (o valor). Isso evita pegar o h3 de outro card.
        """
        ultimo_erro = None
        for _ in range(3):
            try:
                h6 = (
                    page.locator("#csg-page-content h6")
                    .filter(has_text="Cut-off Date")
                    .first
                )
                h6.wait_for(state="visible", timeout=_CUTOFF_TIMEOUT_MS)
                texto = h6.evaluate("""
                    el => {
                        let parent = el.parentElement;
                        while (parent) {
                            const h3 = parent.querySelector('h3');
                            if (h3) return h3.textContent.trim();
                            parent = parent.parentElement;
                            if (!parent || parent.id === 'csg-page-content') break;
                        }
                        return null;
                    }
                """)
                if not texto:
                    raise RuntimeError("h3 não encontrado a partir do h6 Cut-off Date")
                logger.debug("[ConsigNet] Cut-off Date raw: %r", texto)
                return texto
            except Exception as e:
                ultimo_erro = e
                try:
                    page.wait_for_timeout(2000)
                except Exception:
                    pass

        logger.warning("[ConsigNet] Não foi possível extrair Cut-off Date: %s", ultimo_erro)
        return None
