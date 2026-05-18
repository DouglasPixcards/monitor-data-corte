"""Inspeciona a página de login de cada portal e descobre os seletores reais.

Uso:
    python scripts/descobrir_seletores.py
    python scripts/descobrir_seletores.py --portal consignet

Resultado impresso no terminal — nenhuma credencial é usada ou exibida.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

PORTAIS = {
    "consigi":      "https://consigi.com.br/login.xhtml",
    "konexia":      "https://konexia-it.com/login.xhtml",
    "pbconsig":     "https://sso.codata.pb.gov.br/auth/realms/acesso_restrito/protocol/openid-connect/auth?client_id=pbconsig&redirect_uri=https%3A%2F%2Fconsignataria.pbconsig.pb.gov.br%2Flogin&response_mode=fragment&response_type=code&scope=openid",
    "proconsig":    "https://proconsig.com.br/login",
    "consiglog":    "https://saec.consiglog.com.br/Login.aspx",
    "fasitec":      "https://sicon.grupofasitec.com.br/Login.aspx",
    "digitalconsig":"https://sistema.digitalconsig.com.br/",
    "consignet":    "https://www.www1.consignet.com.br/auth/login",
}


def inspecionar(nome: str, url: str, headless: bool = True) -> dict:
    result = {"portal": nome, "url": url, "inputs": [], "buttons": [], "forms": [], "erro": None}

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=headless)
            ctx = browser.new_context()
            page = ctx.new_page()
            page.set_default_timeout(30000)
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

            # Coleta todos os inputs visíveis
            inputs = page.locator("input:visible").all()
            for inp in inputs:
                try:
                    result["inputs"].append({
                        "id": inp.get_attribute("id") or "",
                        "name": inp.get_attribute("name") or "",
                        "type": inp.get_attribute("type") or "text",
                        "placeholder": inp.get_attribute("placeholder") or "",
                        "class": (inp.get_attribute("class") or "")[:60],
                    })
                except Exception:
                    pass

            # Coleta botões
            btns = page.locator("button:visible, input[type='submit']:visible").all()
            for btn in btns:
                try:
                    result["buttons"].append({
                        "id": btn.get_attribute("id") or "",
                        "name": btn.get_attribute("name") or "",
                        "type": btn.get_attribute("type") or "",
                        "text": btn.inner_text()[:80].strip(),
                        "class": (btn.get_attribute("class") or "")[:60],
                    })
                except Exception:
                    pass

            # URL final (pode ter redirecionado)
            result["url_final"] = page.url

            ctx.close()
            browser.close()

    except Exception as e:
        result["erro"] = str(e)

    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--portal", help="Inspecionar apenas este portal")
    parser.add_argument("--headless", action="store_true", default=True)
    args = parser.parse_args()

    portais = PORTAIS
    if args.portal:
        portais = {k: v for k, v in PORTAIS.items() if k == args.portal}

    for nome, url in portais.items():
        print(f"\n{'─'*60}")
        print(f"Portal: {nome}")
        print(f"URL:    {url[:80]}")
        r = inspecionar(nome, url, headless=True)
        if r.get("erro"):
            print(f"  ERRO: {r['erro']}")
        else:
            print(f"  URL final: {r.get('url_final', '')[:80]}")
            print(f"  Inputs ({len(r['inputs'])}):")
            for inp in r["inputs"]:
                print(f"    type={inp['type']:10s} id={inp['id']:30s} name={inp['name']:20s} placeholder={inp['placeholder'][:30]}")
            print(f"  Botões ({len(r['buttons'])}):")
            for btn in r["buttons"]:
                print(f"    id={btn['id']:30s} text={btn['text'][:40]}")


if __name__ == "__main__":
    main()
