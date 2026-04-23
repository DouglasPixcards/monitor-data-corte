def gerar_mensagem_alerta_lote(resultado_lote: dict) -> str:
    linhas = []

    processadora = resultado_lote.get("processadora")
    status = resultado_lote.get("status")
    total_convenios = resultado_lote.get("total_convenios", 0)
    success_count = resultado_lote.get("success_count", 0)
    error_count = resultado_lote.get("error_count", 0)

    linhas.append(f"Processadora: {processadora}")
    linhas.append(f"Status do lote: {status}")
    linhas.append(f"Total de convênios processados: {total_convenios}")
    linhas.append(f"Sucessos: {success_count}")
    linhas.append(f"Erros: {error_count}")

    convenios_ok = [c for c in resultado_lote.get("convenios", []) if c.get("status") == "ok"]
    convenios_erro = [c for c in resultado_lote.get("convenios", []) if c.get("status") != "ok"]

    if convenios_ok:
        linhas.append("")
        linhas.append("Convênios coletados com sucesso:")
        for item in convenios_ok:
            linhas.append(
                f"- {item['convenio_nome']} ({item['convenio_key']}): "
                f"{item['records_count']} registro(s)"
            )

    if convenios_erro:
        linhas.append("")
        linhas.append("Convênios com erro na coleta:")
        for item in convenios_erro:
            linhas.append(
                f"- {item['convenio_nome']} ({item['convenio_key']}): {item['erro']}"
            )

    return "\n".join(linhas)