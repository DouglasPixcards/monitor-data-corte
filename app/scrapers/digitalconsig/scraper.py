"""Scraper para o portal DigitalConsig (sistema.digitalconsig.com.br).

Convênios: Várzea Grande, Vera.

Fluxo:
1. Login em Login.aspx (seletores padrão #txtLogin / #txtSenha / #Entrar)
2. Redireciona para LoginSelecao.aspx — seleciona órgão no <select id="body_ddlOrgao">
3. Clica "Vincular" → navega para Inicial/Inicial.aspx
4. Extrai dia de corte de <span id="body_ConfiguracoesSistema_lbldtcorte">
"""
from __future__ import annotations

import logging
from typing import Any

from app.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

_SUCCESS_URL_FRAGMENTS = ("LoginSelecao.aspx", "Inicial.aspx", "Home", "Dashboard", "Default")
_SUCCESS_INDICATORS = [
    "text=Sair",
    "text=Logout",
    "text=Dashboard",
    "text=Início",
    "text=Bem-Vindo",
    "text=Selecione o Órgão",
    "[class*='dashboard']",
    "[class*='sidebar']",
    "nav",
]

_FAILURE_INDICATORS = [
    "text=Usuário ou senha inválidos",
    "text=Credenciais inválidas",
    "text=Acesso negado",
    "[class*='error']",
    "[class*='alert-danger']",
]


class DigitalconsigScraper(BaseScraper):
    def validate_access(self) -> None:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        current_url = self.page.url
        logger.info("[DigitalConsig] URL após autenticação: %s", current_url)

        if any(fragment in current_url for fragment in _SUCCESS_URL_FRAGMENTS):
            logger.info("[DigitalConsig] Sessão validada por URL: %s", current_url)
            return

        for selector in _FAILURE_INDICATORS:
            try:
                loc = self.page.locator(selector)
                if loc.count() > 0:
                    msg = loc.first.inner_text().strip()
                    raise RuntimeError(
                        f"[DigitalConsig] Autenticação falhou. Mensagem: {msg!r}"
                    )
            except RuntimeError:
                raise
            except Exception:
                pass

        for selector in _SUCCESS_INDICATORS:
            try:
                loc = self.page.locator(selector)
                if loc.count() > 0:
                    logger.info("[DigitalConsig] Sessão validada via seletor: %s", selector)
                    return
            except Exception:
                continue

        logger.warning(
            "[DigitalConsig] Nenhum indicador visual claro — considerado sucesso. URL: %s",
            current_url,
        )

    def collect(self) -> list[dict[str, Any]]:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        self._selecionar_orgao()
        return self._extrair_dia_corte()

    def _selecionar_orgao(self) -> None:
        orgao_texto = self.convenio_config.get("orgao_texto", "")
        if not orgao_texto:
            raise RuntimeError("[DigitalConsig] Campo 'orgao_texto' não configurado para este convênio.")

        # O select é ocultado pelo Chosen.js (display:none) — usa JS para setar valor
        selecionado = self.page.evaluate("""
            (texto) => {
                const select = document.getElementById('body_ddlOrgao');
                if (!select) return null;
                for (const opt of select.options) {
                    if (opt.text.toLowerCase().includes(texto.toLowerCase())) {
                        select.value = opt.value;
                        select.dispatchEvent(new Event('change', { bubbles: true }));
                        return opt.text;
                    }
                }
                return null;
            }
        """, orgao_texto)

        if not selecionado:
            raise RuntimeError(f"[DigitalConsig] Órgão '{orgao_texto}' não encontrado no dropdown.")

        logger.info("[DigitalConsig] Órgão selecionado: %r", selecionado)

        btn = self.page.locator("#body_btnVincular")
        btn.wait_for(state="visible", timeout=10000)
        try:
            with self.page.expect_navigation(wait_until="domcontentloaded", timeout=30000):
                btn.click()
        except Exception:
            pass
        try:
            self.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        logger.info("[DigitalConsig] Navegou para: %s", self.page.url)

    def _extrair_dia_corte(self) -> list[dict[str, Any]]:
        ultimo_erro = None
        for tentativa in range(3):
            try:
                span = self.page.locator("#body_ConfiguracoesSistema_lbldtcorte")
                span.wait_for(state="visible", timeout=15000)
                dia = span.inner_text().strip()
                logger.info("[DigitalConsig] Dia de Corte: %r", dia)
                return [{"folha": None, "mes_atual": None, "data_corte": dia}]
            except Exception as e:
                ultimo_erro = e
                logger.debug("[DigitalConsig] Tentativa %d falhou: %s", tentativa + 1, e)
                try:
                    self.page.wait_for_timeout(2000)
                except Exception:
                    pass

        raise RuntimeError(f"[DigitalConsig] Falha ao extrair Dia de Corte após 3 tentativas: {ultimo_erro}")
