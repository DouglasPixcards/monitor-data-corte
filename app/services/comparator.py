from __future__ import annotations


def _gerar_chave_registro(item: dict) -> str:
    folha = str(item.get("folha", "")).strip()
    mes_atual = str(item.get("mes_atual", "")).strip()
    return f"{folha}|{mes_atual}"


def comparar(dados_anteriores: list[dict], dados_atuais: list[dict]) -> dict:
    resultado = {
        "mudancas": [],
        "novos": [],
        "removidos": [],
        "erros": [],
    }

    mapa_anterior = {
        _gerar_chave_registro(item): item
        for item in dados_anteriores
    }

    mapa_atual = {
        _gerar_chave_registro(item): item
        for item in dados_atuais
    }

    for chave, item_atual in mapa_atual.items():
        if chave not in mapa_anterior:
            resultado["novos"].append({
                "chave": chave,
                "folha": item_atual.get("folha"),
                "mes_atual": item_atual.get("mes_atual"),
                "data_corte": item_atual.get("data_corte"),
            })
            continue

        item_anterior = mapa_anterior[chave]

        data_corte_anterior = item_anterior.get("data_corte")
        data_corte_atual = item_atual.get("data_corte")

        if data_corte_anterior != data_corte_atual:
            resultado["mudancas"].append({
                "chave": chave,
                "folha": item_atual.get("folha"),
                "mes_atual": item_atual.get("mes_atual"),
                "antes": data_corte_anterior,
                "depois": data_corte_atual,
            })

    for chave, item_anterior in mapa_anterior.items():
        if chave not in mapa_atual:
            resultado["removidos"].append({
                "chave": chave,
                "folha": item_anterior.get("folha"),
                "mes_atual": item_anterior.get("mes_atual"),
                "data_corte": item_anterior.get("data_corte"),
            })

    return resultado