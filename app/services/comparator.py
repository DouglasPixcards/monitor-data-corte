def comparar(historico: dict, atual: dict) -> dict:
    resultado = {
        "mudancas": [],
        "novos": [],
        "removidos": [],
        "erros": []
    }

    # Se scraper falhou
    if atual.get("status") != "ok":
        resultado["erros"].append({
            "processadora": atual.get("processadora"),
            "erro": atual.get("erro")
        })
        return resultado

    dados_atuais = {d["convenio"]: d["data_corte"] for d in atual.get("dados", [])}

    # Se não tinha histórico ainda
    if not historico:
        for conv, data in dados_atuais.items():
            resultado["novos"].append({
                "convenio": conv,
                "data_corte": data
            })
        return resultado

    dados_antigos = {d["convenio"]: d["data_corte"] for d in historico.get("dados", [])}

    # Comparar mudanças e novos
    for convenio, data_atual in dados_atuais.items():
        if convenio not in dados_antigos:
            resultado["novos"].append({
                "convenio": convenio,
                "data_corte": data_atual
            })
        else:
            data_antiga = dados_antigos[convenio]
            if data_antiga != data_atual:
                resultado["mudancas"].append({
                    "convenio": convenio,
                    "antes": data_antiga,
                    "depois": data_atual
                })

    # Verificar removidos
    for convenio in dados_antigos:
        if convenio not in dados_atuais:
            resultado["removidos"].append({
                "convenio": convenio,
                "data_corte": dados_antigos[convenio]
            })

    return resultado