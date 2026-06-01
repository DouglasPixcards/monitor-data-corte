"""
Script de diagnóstico para mapear a estrutura do portal ConsigNet pós-login.

Execução:
    cd monitor-data-corte
    python scripts/inspecionar_consignet.py
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

def dump_page(page, titulo: str):
    print(f"\n{'='*60}")
    print(f"  {titulo}")
    print(f"  URL: {page.url}")
    print(f"{'='*60}")
    try:
        body = page.locator("body").inner_text()
        print(body[:3000])
    except Exception as e:
        print(f"  [erro ao ler body]: {e}")

def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        ctx     = browser.new_context()
        page    = ctx.new_page()

        # --- Login (2 etapas) ---
        print(f"\nAcessando {URL_LOGIN} ...")
        page.goto(URL_LOGIN, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)

        # Etapa 1: username
        page.locator("#login-username").fill(USERNAME)
        page.locator("#btn-continue").click()
        page.wait_for_timeout(2000)

        # Etapa 2: password
        page.locator("#login-password").wait_for(state="visible", timeout=15000)
        page.locator("#login-password").fill(PASSWORD)
        page.locator("[id='btn-log in']").click()

        # Aguarda redirecionar para /auth/context
        try:
            page.wait_for_url("**/auth/context**", timeout=30000)
        except Exception:
            pass
        page.wait_for_timeout(3000)

        dump_page(page, "TELA PÓS-LOGIN (/auth/context)")

        # --- Inspeciona elementos relevantes ---
        print("\n--- Elementos interativos na tela de contexto ---")
        for sel in ["button", "a", "mat-card", "mat-list-item", "[class*='context']",
                    "[class*='afilia']", "[class*='convenio']", "[class*='organ']"]:
            try:
                locs = page.locator(sel).all()
                for loc in locs[:5]:
                    txt = loc.inner_text().strip()[:80]
                    if txt:
                        print(f"  {sel}: {txt!r}")
            except Exception:
                pass

        input("\n[PAUSA] Navegue no portal manualmente se quiser. Enter para continuar...")

        dump_page(page, "TELA ATUAL (após navegação manual)")

        # --- Tenta encontrar dados de corte ---
        print("\n--- Buscando seletores de data de corte ---")
        candidatos = [
            "text=corte", "text=Corte", "text=fechamento", "text=Fechamento",
            "text=prazo", "text=Prazo", "text=vencimento",
            "[class*='corte']", "[class*='prazo']", "[class*='fechamento']",
            "td", "th", "mat-cell", "mat-header-cell",
        ]
        for sel in candidatos:
            try:
                locs = page.locator(sel).all()
                for loc in locs[:3]:
                    txt = loc.inner_text().strip()[:120]
                    if txt:
                        print(f"  {sel!r}: {txt!r}")
            except Exception:
                pass

        # HTML completo para análise
        print("\n--- HTML da página atual (primeiros 5000 chars) ---")
        try:
            html = page.content()
            print(html[:5000])
        except Exception as e:
            print(f"Erro: {e}")

        input("\nEnter para fechar o browser...")
        browser.close()

if __name__ == "__main__":
    main()
