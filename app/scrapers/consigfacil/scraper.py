"""Scraper para o portal ConsigFácil (auth por certificado/mTLS).

A validação (fail-closed: consignatario OU correspondente) e a navegação (derivar a URL de
pagina_consignatario a partir do redirect intermediário) são específicas deste portal e ficam
como código.

EXTRAÇÃO — a data de corte vive SOMENTE no card "Datas de Fechamento". A página também tem um
card "Mensagens" cuja tabela traz timestamps de aviso ("15/07/2026 12:06 — Fechamento/Corte:
Agosto/2026"). Quando o perfil do usuário no portal não expõe "Datas de Fechamento", NÃO se
deve cair na tabela de mensagens (isso gerava data falsa como verdade). Por isso ancoramos a
extração no header textual da seção e falhamos tipado se ela não existir.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from app.core.exceptions import CollectionError
from app.scrapers.base_scraper import BaseScraper
from app.scrapers.declarativo import com_retry

logger = logging.getLogger(__name__)

_PAGINA_CONSIGNATARIO = "pagina_consignatario.php"
_CONTROLADOR_PHP = "controlador.php"
_PARAM_CORRESPONDENTE = "pagina=pagina_correspondente.php"

# Card que contém a data real de corte. O seletor ANCORA no texto do header,
# então nunca casa com o card "Mensagens".
_SECAO_DATAS = "Datas de Fechamento"
_CARD_DATAS = f".card:has(.card-header:has-text('{_SECAO_DATAS}'))"
_TIMEOUT_TABELA_MS = 10000
# A data de corte tem de ser uma data pura DD/MM/AAAA. Rejeita timestamp de
# mensagem ("15/07/2026 12:06") e rótulos como "Agosto/2026".
_DATA_PURA = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")


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
            card = self.page.locator(_CARD_DATAS)
            if card.count() == 0:
                # Perfil sem permissão para a seção — NÃO cair na tabela de
                # mensagens. Falha tipada e acionável (checar perfil no portal).
                raise CollectionError(
                    f"Seção '{_SECAO_DATAS}' ausente na página — perfil do usuário no "
                    "portal sem permissão para datas de corte (verificar acesso).",
                    categoria="sem_dado",
                )

            tabela = card.locator("table").first
            tabela.wait_for(state="visible", timeout=_TIMEOUT_TABELA_MS)

            resultados: list[dict[str, Any]] = []
            linhas = tabela.locator("tbody tr")
            for i in range(linhas.count()):
                celulas = linhas.nth(i).locator("td")
                colunas = [celulas.nth(j).inner_text().strip() for j in range(celulas.count())]
                if len(colunas) < 3:
                    continue
                folha, mes_atual, data_corte = colunas[0], colunas[1], colunas[2]
                if not folha and not mes_atual and not data_corte:
                    continue
                if not _DATA_PURA.match(data_corte):
                    logger.warning(
                        "[ConsigFácil] linha ignorada — data_corte não é DD/MM/AAAA: %r "
                        "(folha=%r)", data_corte, folha,
                    )
                    continue
                resultados.append({"folha": folha, "mes_atual": mes_atual, "data_corte": data_corte})

            if not resultados:
                raise CollectionError(
                    f"Seção '{_SECAO_DATAS}' presente mas sem linha de data de corte válida.",
                    categoria="sem_dado",
                )
            return resultados

        return com_retry(self.page, _extrair)
