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

import pyautogui
import time
from datetime import datetime

# Desativa o "fail-safe" (opcional)
# Se você arrastar o mouse para o canto da tela, o script para.
pyautogui.FAILSAFE = True

print("--- Script Anti-Bloqueio Ativado ---")
print("Pressione CTRL+C no terminal para parar.")

try:
    while True:
        # Pressiona e solta a tecla Shift
        pyautogui.press('win')
        
        # Registra o horário no console para você saber que está funcionando
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Tecla pressionada para manter o sistema ativo.")
        
        # Espera 60 segundos antes da próxima execução
        time.sleep(60)
except KeyboardInterrupt:
    print("\nScript encerrado pelo usuário.")
