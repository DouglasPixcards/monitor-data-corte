"""
Dumpeia o HTML completo da tela /auth/context do ConsigNet.
Execução:
    cd monitor-data-corte
    python scripts/dump_consignet_context.py
"""
import sys
sys.path.insert(0, ".")

import os
from dotenv import load_dotenv
load_dotenv(override=True)

from playwright.sync_api import sync_playwright

URL_LOGIN = "https://www.www1.consignet.com.br/auth/login"
USERNAME  = os.getenv("CONSIGNET_DEFENSORIA_USERNAME")
PASSWORD  = os.getenv("CONSIGNET_DEFENSORIA_PASSWORD")


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        ctx  = browser.new_context()
        page = ctx.new_page()

        print(f"Acessando {URL_LOGIN} ...")
        page.goto(URL_LOGIN, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)

        page.locator("#login-username").fill(USERNAME)
        page.locator("#btn-continue").click()
        page.wait_for_timeout(2000)

        page.locator("#login-password").wait_for(state="visible", timeout=15000)
        page.locator("#login-password").fill(PASSWORD)
        page.locator("[id='btn-log in']").click()

        try:
            page.wait_for_url("**/auth/context**", timeout=30000)
        except Exception:
            pass
        page.wait_for_timeout(3000)

        print(f"\nURL atual: {page.url}\n")

        # --- Texto visível ---
        print("=== TEXTO DA PÁGINA (/auth/context) ===")
        try:
            print(page.locator("body").inner_text()[:3000])
        except Exception as e:
            print(f"Erro ao ler texto: {e}")

        # --- Seletores candidatos ---
        print("\n=== SELETORES INTERATIVOS ===")
        candidates = [
            "mat-card", "mat-list-item", "mat-card-title",
            "[class*='context']", "[class*='afilia']", "[class*='card']",
            "[class*='item']", "[class*='organ']", "[role='button']",
            "button", "a", "li",
        ]
        for sel in candidates:
            try:
                locs = page.locator(sel).all()
                for loc in locs[:5]:
                    txt = loc.inner_text().strip()[:100]
                    cls = loc.get_attribute("class") or ""
                    if txt:
                        print(f"  {sel!r:30s} class={cls!r:50s} text={txt!r}")
            except Exception:
                pass

        # --- HTML completo ---
        print("\n=== HTML COMPLETO (primeiros 8000 chars) ===")
        try:
            print(page.content()[:8000])
        except Exception as e:
            print(f"Erro: {e}")

        browser.close()


if __name__ == "__main__":
    main()
