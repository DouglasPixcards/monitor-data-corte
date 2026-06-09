"""Diagnóstico do login ConsigNet — captura evidência no ponto da falha.

Reproduz exatamente o fluxo de autenticação usado pela coleta (mesmas
factories build_auth_strategy / build_scraper), mas NÃO fecha o browser antes
de capturar: screenshot, HTML, estado dos campos de login e mensagens visíveis.

Objetivo: distinguir entre credencial rejeitada, captcha/desafio, bloqueio de
rate-limit ou mudança de seletor/fluxo no portal.

Uso:
    python scripts/diag_consignet.py                 # defensoria (default)
    python scripts/diag_consignet.py --convenio vilhena
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("diag_consignet")

from app.core.loader import load_processadoras_config
from app.services.coleta_service import build_auth_strategy, build_scraper

_OUT_DIR = Path("data") / "diagnostico"


def _safe(fn, default=None):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        return f"<erro: {e}>" if default is None else default


def _inspecionar_campos(page, selectors: dict) -> None:
    """Reporta existência, visibilidade e valor de cada seletor de login."""
    logger.info("── Estado dos campos de login ──")
    for key in ("step1_username", "step1_submit", "step2_password", "step2_submit"):
        sel = selectors.get(key)
        if not sel:
            continue
        css = sel.get("value") or f"role={sel.get('role')}:{sel.get('name')}"
        loc = page.locator(sel["value"]) if sel["type"] == "css" else page.get_by_role(sel["role"], name=sel.get("name"))
        count = _safe(lambda: loc.count(), 0)
        visivel = _safe(lambda: loc.first.is_visible() if count else False, False)
        habilitado = _safe(lambda: loc.first.is_enabled() if count else False, False)
        valor = _safe(lambda: loc.first.input_value() if count else "", "")
        # Mascara senha
        if key == "step2_password" and isinstance(valor, str) and valor:
            valor = f"<preenchido: {len(valor)} chars>"
        logger.info("  %-15s %-28s count=%s visivel=%s enabled=%s valor=%r",
                    key, css, count, visivel, habilitado, valor)


def _coletar_mensagens(page) -> None:
    """Procura toasts, alertas e mensagens de erro visíveis na tela."""
    logger.info("── Mensagens / alertas na tela ──")
    seletores_msg = [
        "[role='alert']", "[class*='alert']", "[class*='error']",
        "[class*='toast']", "[class*='invalid']", "[class*='danger']",
        "[class*='captcha']", "iframe[src*='recaptcha']", "iframe[title*='captcha']",
    ]
    achou = False
    for sel in seletores_msg:
        loc = page.locator(sel)
        count = _safe(lambda: loc.count(), 0)
        if not count:
            continue
        for i in range(min(count, 5)):
            el = loc.nth(i)
            if _safe(lambda: el.is_visible(), False):
                txt = _safe(lambda: el.inner_text().strip(), "")
                if txt or "captcha" in sel or "iframe" in sel:
                    achou = True
                    logger.info("  [%s #%d] %r", sel, i, txt[:200] if txt else "<elemento presente>")
    if not achou:
        logger.info("  (nenhum alerta/toast/captcha visível encontrado)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnóstico do login ConsigNet.")
    parser.add_argument("--convenio", default="defensoria", help="Convênio consignet (default: defensoria)")
    args = parser.parse_args()

    config = load_processadoras_config()
    convenio_config = config["convenios"].get(args.convenio)
    if not convenio_config:
        logger.error("Convênio %r não encontrado.", args.convenio)
        return 1
    if convenio_config["processadora"] != "consignet":
        logger.error("Convênio %r não é consignet (é %s).", args.convenio, convenio_config["processadora"])
        return 1

    processadora_config = config["processadoras"]["consignet"]
    selectors = processadora_config["selectors"]

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = _OUT_DIR / f"consignet_{args.convenio}_{ts}"

    auth = build_auth_strategy(processadora_config, convenio_config)
    scraper = build_scraper("consignet", processadora_config, convenio_config, auth)

    logger.info("[Diag] Iniciando login de %r (afiliacao=%r)",
                args.convenio, convenio_config.get("afiliacao"))
    scraper.start()
    try:
        try:
            scraper.authenticate()
        except Exception as e:  # noqa: BLE001
            logger.warning("[Diag] authenticate() lançou: %s", e)

        page = scraper.page
        logger.info("[Diag] URL final: %s", _safe(lambda: page.url))

        # Captura screenshot + HTML antes de fechar
        png = base.with_suffix(".png")
        html = base.with_suffix(".html")
        _safe(lambda: page.screenshot(path=str(png), full_page=True))
        _safe(lambda: html.write_text(page.content(), encoding="utf-8"))
        logger.info("[Diag] Screenshot: %s", png)
        logger.info("[Diag] HTML:       %s", html)

        _inspecionar_campos(page, selectors)
        _coletar_mensagens(page)

        # Primeiros 600 chars do texto visível do body — costuma conter a mensagem do portal
        body_txt = _safe(lambda: page.locator("body").inner_text().strip(), "")
        if isinstance(body_txt, str) and body_txt:
            logger.info("── Texto visível (body, 600 chars) ──\n%s", body_txt[:600])
    finally:
        scraper.stop()

    logger.info("[Diag] Concluído. Verifique os arquivos em %s", _OUT_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
