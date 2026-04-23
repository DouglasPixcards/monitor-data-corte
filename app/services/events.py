from __future__ import annotations

import uuid

from app.services.storage_helpers import now_iso


def comparacao_para_eventos(
    processadora: str,
    comparacao: dict,
    execution_id: str,
    snapshot_id: str,
) -> list[dict]:
    eventos: list[dict] = []
    detected_at = now_iso()

    for item in comparacao.get("mudancas", []):
        eventos.append({
            "event_id": str(uuid.uuid4()),
            "event_type": "data_corte_alterada",
            "processadora": processadora,
            "execution_id": execution_id,
            "snapshot_id": snapshot_id,
            "detected_at": detected_at,
            "record_key": item["chave"],
            "folha": item.get("folha"),
            "mes_atual": item.get("mes_atual"),
            "before": {
                "data_corte": item.get("antes"),
            },
            "after": {
                "data_corte": item.get("depois"),
            },
        })

    for item in comparacao.get("novos", []):
        eventos.append({
            "event_id": str(uuid.uuid4()),
            "event_type": "registro_novo",
            "processadora": processadora,
            "execution_id": execution_id,
            "snapshot_id": snapshot_id,
            "detected_at": detected_at,
            "record_key": item["chave"],
            "folha": item.get("folha"),
            "mes_atual": item.get("mes_atual"),
            "before": None,
            "after": {
                "data_corte": item.get("data_corte"),
            },
        })

    for item in comparacao.get("removidos", []):
        eventos.append({
            "event_id": str(uuid.uuid4()),
            "event_type": "registro_removido",
            "processadora": processadora,
            "execution_id": execution_id,
            "snapshot_id": snapshot_id,
            "detected_at": detected_at,
            "record_key": item["chave"],
            "folha": item.get("folha"),
            "mes_atual": item.get("mes_atual"),
            "before": {
                "data_corte": item.get("data_corte"),
            },
            "after": None,
        })

    for item in comparacao.get("erros", []):
        eventos.append({
            "event_id": str(uuid.uuid4()),
            "event_type": "erro_coleta",
            "processadora": processadora,
            "execution_id": execution_id,
            "snapshot_id": snapshot_id,
            "detected_at": detected_at,
            "record_key": None,
            "folha": None,
            "mes_atual": None,
            "before": None,
            "after": {
                "erro": item.get("erro"),
            },
        })

    return eventos