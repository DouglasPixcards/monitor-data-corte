# from app.services.collector_service import executar_coleta
from __future__ import annotations

from app.services.orchestrator_factory import build_orchestrator


def run() -> None:
    # processadora = "consigup"
    # executar_coleta(processadora)

    try:
        execucao = build_orchestrator().executar("consigfacil")
        return {
            "id": execucao.id,
            "processadora": execucao.processadora,
            "status": execucao.status,
            "executada_em": execucao.executada_em,
            "total_convenios": execucao.total_convenios,
            "success_count": execucao.success_count,
            "error_count": execucao.error_count,
        }
    except ValueError as e:
        raise print(f"Erro ao executar coleta: {e}") from e
if __name__ == "__main__":
    run()