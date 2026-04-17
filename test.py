from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        channel="chrome",  # usa o Chrome real com policy
        headless=False
    )

    context = browser.new_context()
    page = context.new_page()

    page.goto("https://www.faciltecnologia.com.br/consigfacil/belterra/validar_certificado_cliente.php")

    input("Veja se entrou direto...")

