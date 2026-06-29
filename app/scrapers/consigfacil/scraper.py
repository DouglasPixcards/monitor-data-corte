"""Scraper para o portal ConsigFácil (auth por certificado/mTLS).

A validação (fail-closed: consignatario OU correspondente) e a navegação (derivar a URL de
pagina_consignatario a partir do redirect intermediário) são específicas deste portal e ficam
como código. A EXTRAÇÃO da tabela adota os helpers do framework (linhas_de_tabela + com_retry).
"""
from __future__ import annotations

import logging
from typing import Any

from app.scrapers.base_scraper import BaseScraper
from app.scrapers.declarativo import com_retry, linhas_de_tabela

logger = logging.getLogger(__name__)

_PAGINA_CONSIGNATARIO = "pagina_consignatario.php"
_CONTROLADOR_PHP = "controlador.php"
_PARAM_CORRESPONDENTE = "pagina=pagina_correspondente.php"


def _url_e_consignatario(url: str) -> bool:
    return _PAGINA_CONSIGNATARIO in url


def _url_e_correspondente(url: str) -> bool:
    """True somente se a URL for exatamente o redirect alternativo conhecido."""
    return _CONTROLADOR_PHP in url and _PARAM_CORRESPONDENTE in url


class ConsigFacilScraper(BaseScraper):
    def validate_access(self) -> None:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        url_atual = self.page.url
        logger.info("[ConsigFácil] URL após autenticação: %s", url_atual)

        if _url_e_consignatario(url_atual):
            logger.info("[ConsigFácil] Acesso validado via pagina_consignatario.php")
            return
        if _url_e_correspondente(url_atual):
            logger.info(
                "[ConsigFácil] Validado via pagina_correspondente — navegação adicional em collect()"
            )
            return

        raise RuntimeError(f"Acesso não validado. URL atual: {url_atual}")

    def _navegar_para_consignatario_se_necessario(self) -> None:
        """Se estiver na URL intermediária, navega até pagina_consignatario.php."""
        if not _url_e_correspondente(self.page.url):
            return
        base = self.get_target_url().rsplit("/", 1)[0]
        destino = f"{base}/{_PAGINA_CONSIGNATARIO}"
        logger.info("[ConsigFácil] Navegando de pagina_correspondente para: %s", destino)
        self.page.goto(destino, wait_until="domcontentloaded", timeout=self.timeout)
        logger.info("[ConsigFácil] URL após navegação: %s", self.page.url)

    def collect(self) -> list[dict[str, Any]]:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        self._navegar_para_consignatario_se_necessario()

        def _extrair() -> list[dict[str, Any]]:
            resultados: list[dict[str, Any]] = []
            linhas = linhas_de_tabela(
                self.page, "table.table.table-consig-info", timeout=10000, linhas_seletor="tbody tr"
            )
            for colunas in linhas:
                if len(colunas) < 3:
                    continue
                folha, mes_atual, data_corte = colunas[0], colunas[1], colunas[2]
                if not folha and not mes_atual and not data_corte:
                    continue
                resultados.append({"folha": folha, "mes_atual": mes_atual, "data_corte": data_corte})
            return resultados

        return com_retry(self.page, _extrair)
