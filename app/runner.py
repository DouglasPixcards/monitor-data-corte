from app.services.coleta_service import executar_coleta
from app.services.comparator import comparar
from app.services.alert import gerar_mensagem_alerta
from app.services.storage_helpers import (
    now_iso,
    make_hash,
    make_snapshot_id,
    make_execution_id,
)
from app.storage.file_storage import FileStorageRepository


def run() -> None:
    storage = FileStorageRepository(base_path="data")

    resultado = executar_coleta("belterra")
    processadora = resultado.get("processadora", "desconhecida")

    print("\n=== RESULTADO DA COLETA ===")
    print(resultado)

    execution = {
        "execution_id": make_execution_id(),
        "processadora": processadora,
        "convenio": resultado.get("convenio"),
        "executed_at": now_iso(),
        "status": resultado.get("status"),
        "records_count": len(resultado.get("dados", [])),
        "error_message": resultado.get("erro"),
        "result_hash": make_hash(resultado.get("dados", [])),
    }

    storage.save_execution(processadora, execution)

    if resultado.get("status") != "ok":
        print("\n=== ERRO NA COLETA ===")
        print(resultado.get("erro"))
        return

    snapshot = {
        "snapshot_id": make_snapshot_id(),
        "execution_id": execution["execution_id"],
        "processadora": processadora,
        "convenio": resultado.get("convenio"),
        "collected_at": now_iso(),
        "records": resultado.get("dados", []),
    }

    latest_anterior = storage.load_latest_snapshot(processadora)

    dados_anteriores = latest_anterior["records"] if latest_anterior else []
    dados_atuais = snapshot["records"]

    # comparacao = comparar(dados_anteriores, dados_atuais)
    # mensagem = gerar_mensagem_alerta(comparacao)

    print("\n=== RESULTADO DA COMPARAÇÃO ===")
    # print(mensagem)

    storage.save_snapshot(processadora, snapshot)
    storage.save_latest_snapshot(processadora, snapshot)


if __name__ == "__main__":
    run()