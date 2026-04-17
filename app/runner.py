from app.scrapers.ConsigFacil.consigfacil import coletar
from app.services.storage import (
    carregar_historico,
    salvar_historico,
    salvar_ultimo_resultado,
)
from app.services.comparator import comparar
from app.services.alert import gerar_mensagem_alerta


def run() -> None:
    historico = carregar_historico()
    resultado = coletar()

    print("\n=== RESULTADO DA COLETA ===")
    print(resultado)

    salvar_ultimo_resultado(resultado)

    if resultado.get("status") != "ok":
        print("\n=== ERRO NA COLETA ===")
        print(resultado.get("erro"))
        return

    comparacao = comparar(historico, resultado)
    mensagem = gerar_mensagem_alerta(comparacao)

    print("\n=== RESULTADO DA COMPARAÇÃO ===")
    print(mensagem)

    salvar_historico(resultado)


if __name__ == "__main__":
    run()