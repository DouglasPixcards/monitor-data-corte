def gerar_mensagem_alerta(comparacao: dict) -> str:
    linhas = []

    if comparacao["mudancas"]:
        linhas.append("Mudanças de data de corte:")
        for item in comparacao["mudancas"]:
            linhas.append(
                f"- Convênio {item['convenio']}: {item['antes']} -> {item['depois']}"
            )

    if comparacao["novos"]:
        linhas.append("Novos convênios encontrados:")
        for item in comparacao["novos"]:
            linhas.append(
                f"- Convênio {item['convenio']}: {item['data_corte']}"
            )

    if comparacao["removidos"]:
        linhas.append("Convênios removidos:")
        for item in comparacao["removidos"]:
            linhas.append(
                f"- Convênio {item['convenio']}: {item['data_corte']}"
            )

    if comparacao["erros"]:
        linhas.append("Erros na coleta:")
        for item in comparacao["erros"]:
            linhas.append(
                f"- {item['processadora']}: {item['erro']}"
            )

    if not linhas:
        return "Nenhuma alteração encontrada."

    return "\n".join(linhas)