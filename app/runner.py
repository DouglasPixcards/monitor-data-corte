from app.scrapers.processadora_a import coletar
from app.services.storage import carregar_historico, salvar_historico, salvar_ultimo_resultado
from app.services.comparator import comparar
from app.services.alert import gerar_mensagem_alerta


def run():
    historico = carregar_historico()
    resultado = coletar()

    comparacao = comparar(historico, resultado)
    mensagem = gerar_mensagem_alerta(comparacao)

    print("\n=== RESULTADO DA COMPARAÇÃO ===")
    print(mensagem)

    salvar_ultimo_resultado(resultado)
    salvar_historico(resultado)