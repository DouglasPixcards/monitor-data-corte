from __future__ import annotations

import logging
from typing import Any

from app.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# URL da tela de consulta de datas de corte (caminho relativo ao slug do convênio)
_PAGINA_CONSIGNATARIO = "pagina_consignatario.php"

# URL alternativa pós-login observada em alguns convênios (maranhao, itaituba).
# Aceita apenas quando AMBAS as partes estiverem presentes na URL.
_CONTROLADOR_PHP = "controlador.php"
_PARAM_CORRESPONDENTE = "pagina=pagina_correspondente.php"


def _url_e_consignatario(url: str) -> bool:
    return _PAGINA_CONSIGNATARIO in url


def _url_e_correspondente(url: str) -> bool:
    """Retorna True somente se a URL for exatamente o redirect alternativo conhecido."""
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
            # Portal redirecionou para página intermediária após certificado aceito.
            # collect() navegará até pagina_consignatario.php antes de extrair dados.
            logger.info(
                "[ConsigFácil] Acesso validado via controlador.php?pagina=pagina_correspondente.php"
                " — navegação adicional será feita em collect()"
            )
            return

        raise RuntimeError(f"Acesso não validado. URL atual: {url_atual}")

    def _navegar_para_consignatario_se_necessario(self) -> None:
        """Se estiver na URL intermediária, navega até pagina_consignatario.php."""
        if not _url_e_correspondente(self.page.url):
            return

        # Deriva a URL de destino a partir do target_url do convênio.
        # Ex.: .../consigfacil/maranhao/validar_certificado_cliente.php
        #   → .../consigfacil/maranhao/pagina_consignatario.php
        base = self.get_target_url().rsplit("/", 1)[0]
        destino = f"{base}/{_PAGINA_CONSIGNATARIO}"

        logger.info("[ConsigFácil] Navegando de pagina_correspondente para: %s", destino)
        self.page.goto(destino, wait_until="domcontentloaded", timeout=self.timeout)
        logger.info("[ConsigFácil] URL após navegação: %s", self.page.url)

    def collect(self) -> list[dict[str, Any]]:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")

        self._navegar_para_consignatario_se_necessario()

        ultimo_erro = None

        for tentativa in range(3):
            try:
                tabela = self.page.locator("table.table.table-consig-info").first
                tabela.wait_for(state="visible", timeout=10000)

                linhas = tabela.locator("tbody tr")
                quantidade_linhas = linhas.count()

                resultados: list[dict[str, Any]] = []

                for i in range(quantidade_linhas):
                    linha = linhas.nth(i)
                    colunas = linha.locator("td")
                    quantidade_colunas = colunas.count()

                    if quantidade_colunas < 3:
                        continue

                    folha = colunas.nth(0).inner_text().strip()
                    mes_atual = colunas.nth(1).inner_text().strip()
                    data_corte = colunas.nth(2).inner_text().strip()

                    if not folha and not mes_atual and not data_corte:
                        continue

                    resultados.append(
                        {
                            "folha": folha,
                            "mes_atual": mes_atual,
                            "data_corte": data_corte,
                        }
                    )

                return resultados

            except Exception as e:
                ultimo_erro = e
                self.page.wait_for_timeout(2000)

        raise RuntimeError(f"Falha ao coletar dados da tabela de fechamento: {ultimo_erro}")