from __future__ import annotations

from app.services.coleta_service import executar_coleta_lote
from app.services.alert import gerar_mensagem_alerta_lote
from app.services.storage_helpers import (
    now_iso,
    make_hash,
    make_snapshot_id,
    make_execution_id,
)
from app.storage.file_storage import FileStorageRepository


def executar_coleta(processadora: str) -> dict:
    storage = FileStorageRepository(base_path="data")

    resultado_lote = executar_coleta_lote(processadora)

    print("\n=== RESULTADO DA COLETA ===")
    print(resultado_lote)

    # =========================
    # EXECUTION (sempre salva)
    # =========================
    execution = {
        "execution_id": make_execution_id(),
        "processadora": resultado_lote.get("processadora"),
        "executed_at": now_iso(),
        "status": resultado_lote.get("status"),
        "total_convenios": resultado_lote.get("total_convenios"),
        "success_count": resultado_lote.get("success_count"),
        "error_count": resultado_lote.get("error_count"),
        "records_count": len(resultado_lote.get("records", [])),
        "result_hash": make_hash(resultado_lote.get("records", [])),
        "convenios": resultado_lote.get("convenios", []),
    }

    storage.save_execution(processadora, execution)

    # =========================
    # SNAPSHOT (somente dados válidos)
    # =========================
    snapshot = {
        "snapshot_id": make_snapshot_id(),
        "execution_id": execution["execution_id"],
        "processadora": processadora,
        "collected_at": now_iso(),
        "records": resultado_lote.get("records", []),
    }

    storage.save_snapshot(processadora, snapshot)
    storage.save_latest_snapshot(processadora, snapshot)

    # =========================
    # ALERTA
    # =========================
    mensagem = gerar_mensagem_alerta_lote(resultado_lote)

    print("\n=== ALERTA DO LOTE ===")
    print(mensagem)

    return execution