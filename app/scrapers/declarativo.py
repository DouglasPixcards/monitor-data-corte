"""Framework declarativo para scrapers Playwright SIMPLES.

- `validar_acesso(page, regras, timeout)`: validate_access dirigido por config.
- helpers de extração reusáveis (texto / tabela / regex).
- `ScraperDeclarativo`: base que implementa `validate_access` a partir de
  `processadora_config["validacao"]`; o scraper concreto só escreve um `collect()` curto.

Scrapers complexos (ConsigNet, Fasitec, ConsigLog, DigitalConsig) continuam como override —
a extração e a navegação deles são diversas demais para config.
"""
from __future__ import annotations

import logging
import re

from app.core.exceptions import CollectionError
from app.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

_TIMEOUT_EXTRACAO_MS = 15000


def _categoria_keyword(kw: str) -> str:
    return "credencial_expirada" if "xpirad" in kw.lower() else "auth_falhou"


def _presente(page, seletor: str) -> bool:
    try:
        return page.locator(seletor).count() > 0
    except Exception:  # noqa: BLE001 — seletor inválido = ausente
        return False


def _texto_corpo(page) -> str:
    try:
        return page.locator("body").inner_text()
    except Exception:  # noqa: BLE001
        return ""


def validar_acesso(page, regras: dict, timeout: int) -> None:
    """Valida o acesso pós-login a partir de regras declarativas (todas opcionais):

    - `aguardar_url`: padrão glob — espera a URL antes de validar (redirect pós-auth).
    - `falha_url`: fragmentos de URL que indicam que NÃO logou (ainda na tela de login).
    - `falha_seletores` / `falha_keywords`: presença = falha (CollectionError tipado —
      `credencial_expirada` se a keyword contém "xpirad", senão `auth_falhou`).
    - `sucesso_url` / `sucesso_seletores`: presença de qualquer um = sucesso.

    Sem sinal conclusivo → warning + considera ok (não bloqueia).
    """
    if not regras:
        return

    aguardar = regras.get("aguardar_url")
    if aguardar:
        page.wait_for_url(aguardar, timeout=timeout)

    # 1) Falha explícita primeiro.
    for sel in regras.get("falha_seletores", []):
        if _presente(page, sel):
            raise CollectionError(f"Indicador de falha presente: {sel}", categoria="auth_falhou")

    keywords = regras.get("falha_keywords", [])
    if keywords:
        corpo = _texto_corpo(page).lower()
        for kw in keywords:
            if kw.lower() in corpo:
                raise CollectionError(f"Falha de acesso: '{kw}'", categoria=_categoria_keyword(kw))

    for frag in regras.get("falha_url", []):
        if frag in page.url:
            raise CollectionError(f"Ainda na tela de login ({frag})", categoria="auth_falhou")

    # 2) Sucesso.
    for frag in regras.get("sucesso_url", []):
        if frag in page.url:
            return
    for sel in regras.get("sucesso_seletores", []):
        if _presente(page, sel):
            return

    # aguardar_url satisfeito (sem falha detectada) já é, por si, o sinal de sucesso.
    if aguardar:
        return

    logger.warning("[validacao] sem sinal conclusivo — considerado ok. URL: %s", page.url)


# ── Helpers de extração ───────────────────────────────────────────────────────

def texto_apos_separador(page, seletor: str, sep: str = ":", timeout: int = _TIMEOUT_EXTRACAO_MS) -> str:
    """Espera o elemento visível, pega o inner_text e devolve o trecho após o último `sep`."""
    loc = page.locator(seletor)
    loc.wait_for(state="visible", timeout=timeout)
    return loc.inner_text().split(sep)[-1].strip()


def valor_opcional_apos_separador(page, seletor: str, sep: str = ":") -> str | None:
    """Como `texto_apos_separador`, mas devolve None se o elemento não existir."""
    loc = page.locator(seletor)
    if loc.count() == 0:
        return None
    return loc.inner_text().split(sep)[-1].strip()


def linhas_de_tabela(page, seletor: str, timeout: int = _TIMEOUT_EXTRACAO_MS) -> list[list[str]]:
    """Espera a tabela e devolve as linhas como listas de textos de célula (td)."""
    tabela = page.locator(seletor)
    tabela.wait_for(timeout=timeout)
    linhas = tabela.locator("tr")
    out: list[list[str]] = []
    for i in range(linhas.count()):
        celulas = linhas.nth(i).locator("td")
        out.append([celulas.nth(j).inner_text().strip() for j in range(celulas.count())])
    return out


def primeiro_grupo_regex(texto: str, padrao: str, grupo: int = 1) -> str | None:
    """re.search puro (case-insensitive): devolve o grupo capturado (ou None)."""
    m = re.search(padrao, texto or "", re.IGNORECASE)
    return m.group(grupo) if m else None


def com_retry(page, fn, tentativas: int = 3, espera_ms: int = 2000):
    """Tenta `fn()` até `tentativas` vezes (espera entre tentativas) — para extrações
    flaky de portais JSF/PrimeFaces. Re-levanta a última exceção se todas falharem."""
    ultimo: Exception | None = None
    for i in range(tentativas):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            ultimo = exc
            if i < tentativas - 1:
                page.wait_for_timeout(espera_ms)
    raise ultimo


# ── Base declarativa ──────────────────────────────────────────────────────────

class ScraperDeclarativo(BaseScraper):
    """Base para scrapers simples: `validate_access` vem de `processadora_config['validacao']`.
    O scraper concreto só implementa `collect()` (curto, com os helpers acima)."""

    def validate_access(self) -> None:
        if self.page is None:
            raise RuntimeError("Page não inicializada.")
        validar_acesso(self.page, self.processadora_config.get("validacao", {}), self.timeout)
