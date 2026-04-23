from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.storage.file_storage import FileStorageRepository
from app.services.collector_service import executar_coleta


app = FastAPI(title="Pipeline Corte API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


storage = FileStorageRepository(base_path="data")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/coletas/{processadora}/ultimo_resultado")
def obter_ultimo_resultado(processadora: str) -> dict:
    resultado = storage.load_latest_execution(processadora)

    if not resultado:
        return {
            "execution_id": None,
            "processadora": processadora,
            "executed_at": None,
            "status": "empty",
            "total_convenios": 0,
            "success_count": 0,
            "error_count": 0,
            "records_count": 0,
            "convenios": [],
        }

    return resultado

@app.get("/coletas/{processadora}/historico")
def obter_historico(processadora: str) -> list[dict]:
    return storage.load_all_executions(processadora)

@app.post("/coletas/{processadora}/executar")
def executar_coleta_endpoint(processadora: str) -> dict:
    try:
        return executar_coleta(processadora)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))