# from playwright.sync_api import sync_playwright

# with sync_playwright() as p:
#     browser = p.chromium.launch(
#         channel="chrome",  # usa o Chrome real com policy
#         headless=False
#     )

#     context = browser.new_context()
#     page = context.new_page()

#     page.goto("https://www.faciltecnologia.com.br/consigfacil/belterra/validar_certificado_cliente.php")

#     input("Veja se entrou direto...")

# import pyautogui
# import time
# from datetime import datetime

# # Desativa o "fail-safe" (opcional)
# # Se você arrastar o mouse para o canto da tela, o script para.
# pyautogui.FAILSAFE = True

# print("--- Script Anti-Bloqueio Ativado ---")
# print("Pressione CTRL+C no terminal para parar.")

# try:
#     while True:
#         # Pressiona e solta a tecla Shift
#         pyautogui.press('win')
        
#         # Registra o horário no console para você saber que está funcionando
#         timestamp = datetime.now().strftime("%H:%M:%S")
#         print(f"[{timestamp}] Tecla pressionada para manter o sistema ativo.")
        
#         # Espera 60 segundos antes da próxima execução
#         time.sleep(60)
# except KeyboardInterrupt:
#     print("\nScript encerrado pelo usuário.")


import pandas as pd

# Cole seu JSON aqui dentro (como lista)
data = [
        {
            "convenio_key": "belterra",
            "convenio_nome": "Belterra",
            "status": "erro",
            "records_count": 0,
            "erro": "Acesso não validado. URL atual: https://www.faciltecnologia.com.br/consigfacil/belterra/validar_certificado_cliente.php",
            "dados": []
        },
        {
            "convenio_key": "maranhao",
            "convenio_nome": "Maranhão",
            "status": "erro",
            "records_count": 0,
            "erro": "Acesso não validado. URL atual: https://www.faciltecnologia.com.br/consigfacil/maranhao/controlador.php?pagina=pagina_correspondente.php",
            "dados": []
        },
        {
            "convenio_key": "santarem",
            "convenio_nome": "Santarém",
            "status": "ok",
            "records_count": 1,
            "erro": None,
            "dados": [
                {
                    "folha": "Prefeitura de Santarém",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "13/05/2026"
                }
            ]
        },
        {
            "convenio_key": "ipatingamg",
            "convenio_nome": "Ipatinga MG",
            "status": "ok",
            "records_count": 1,
            "erro": None,
            "dados": [
                {
                    "folha": "Prefeitura Municipal de Ipatinga",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "15/05/2026"
                }
            ]
        },
        {
            "convenio_key": "cuiaba",
            "convenio_nome": "Cuiabá",
            "status": "ok",
            "records_count": 2,
            "erro": None,
            "dados": [
                {
                    "folha": "Cuiabá Prev",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "08/05/2026"
                },
                {
                    "folha": "Prefeitura de Cuiabá",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "08/05/2026"
                }
            ]
        },
        {
            "convenio_key": "portovelho",
            "convenio_nome": "Porto Velho",
            "status": "ok",
            "records_count": 1,
            "erro": None,
            "dados": [
                {
                    "folha": "Prefeitura de Porto Velho",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "05/05/2026"
                }
            ]
        },
        {
            "convenio_key": "teresina",
            "convenio_nome": "Teresina",
            "status": "ok",
            "records_count": 17,
            "erro": None,
            "dados": [
                {
                    "folha": "ARSETE",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "18/05/2026"
                },
                {
                    "folha": "ETURB - Emp. Ter. Des. Urbano",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "18/05/2026"
                },
                {
                    "folha": "FCMC - Fund. Cult. Mons. Chaves",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "18/05/2026"
                },
                {
                    "folha": "FMS - Fund. Mun. de Saúde",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "18/05/2026"
                },
                {
                    "folha": "FWF - Fundação Wall Ferraz",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "18/05/2026"
                },
                {
                    "folha": "IPMT - Instituto de Previdência",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "18/05/2026"
                },
                {
                    "folha": "PARL - Parlamentar",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "18/05/2026"
                },
                {
                    "folha": "Prefeitura Municipal de Teresina",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "18/05/2026"
                },
                {
                    "folha": "PRODATER",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "18/05/2026"
                },
                {
                    "folha": "SAAD Centro",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "18/05/2026"
                },
                {
                    "folha": "SAAD Leste",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "18/05/2026"
                },
                {
                    "folha": "SAAD Norte",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "18/05/2026"
                },
                {
                    "folha": "SAAD Rural",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "18/05/2026"
                },
                {
                    "folha": "SAAD Sudeste",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "18/05/2026"
                },
                {
                    "folha": "SAAD Sudeste II",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "18/05/2026"
                },
                {
                    "folha": "SAAD Sul",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "18/05/2026"
                },
                {
                    "folha": "STRANS",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "18/05/2026"
                }
            ]
        },
        {
            "convenio_key": "itaituba",
            "convenio_nome": "Itaituba",
            "status": "erro",
            "records_count": 0,
            "erro": "Acesso não validado. URL atual: https://www.faciltecnologia.com.br/consigfacil/itaituba/controlador.php?pagina=pagina_correspondente.php",
            "dados": []
        },
        {
            "convenio_key": "mt",
            "convenio_nome": "Portal do Consignado MT",
            "status": "ok",
            "records_count": 3,
            "erro": None,
            "dados": [
                {
                    "folha": "EMPAER",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "14/05/2026"
                },
                {
                    "folha": "MTI",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "14/05/2026"
                },
                {
                    "folha": "SEPLAG",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "14/05/2026"
                }
            ]
        },
        {
            "convenio_key": "piaui",
            "convenio_nome": "ConsigFácil PI",
            "status": "ok",
            "records_count": 1,
            "erro": None,
            "dados": [
                {
                    "folha": "Governo do Estado do Piauí",
                    "mes_atual": "Maio de 2026",
                    "data_corte": "05/05/2026"
                }
            ]
        }
    ]

linhas = []

for item in data:
    convenio_nome = item.get("convenio_nome")
    dados = item.get("dados", [])

    for d in dados:
        linhas.append({
            "convenio": convenio_nome,
            "folha": d.get("folha"),
            "mes_atual": d.get("mes_atual"),
            "data_corte": d.get("data_corte")
        })

# Criar DataFrame
df = pd.DataFrame(linhas)

# Ordenar por data (opcional)
df["data_corte"] = pd.to_datetime(df["data_corte"], format="%d/%m/%Y", errors="coerce")
df = df.sort_values("data_corte")

# Salvar Excel
df.to_excel("datas_corte.xlsx", index=False)

print("Excel gerado com sucesso!")