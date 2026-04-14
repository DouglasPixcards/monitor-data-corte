# instalar o playwright

# pip install playwright
# playwright install

# abrir um navegador

from playwright.sync_api import sync_playwright, expect

with sync_playwright() as pw:
    navegador = pw.chromium.launch(headless=False)
    contexto = navegador.new_context()
    # abrir o navegador
    pagina = contexto.new_page()

    # navegar para uma página
    pagina.goto("https://www.hashtagtreinamentos.com/")

    # pegar infos da página
    print(pagina.title())

    # selecionar um elemento na tela
    # 1ªforma: xpath
    # pagina.locator('xpath=/html/body/main/section[1]/div[2]/a').click()
    # 2ªforma: get_by
    botao = pagina.locator("div").filter(has_text="Torne-se uma referência no").get_by_role("link")
    with contexto.expect_page() as pagina2_info:
        botao.click()

    # selecionar varios elementos
    # links = pagina.get_by_role("link").all()
    # for link in links:
    #     print(link)
    
    # nova página em branco
    # pagina2 = contexto.new_page()

    # nova página -> criar contextos e depois:
    pagina2 = pagina2_info.value
    pagina2.goto("https://www.hashtagtreinamentos.com/curso-python")

    # preencher formulario
    pagina2.get_by_role("textbox", name="Seu primeiro nome").fill("Joao")
    pagina2.get_by_role("textbox", name="Seu melhor e-mail").fill("pythonimpressionador@gmail.com")
    pagina2.get_by_role("button", name="Quero acessar as informações").click()

    # esperar um elemento na tela
    novo_botao = pagina2.get_by_role("link", name="quero garantir uma vaga")
    expect(novo_botao).to_be_visible()
    novo_botao.click()

    navegador.close()

