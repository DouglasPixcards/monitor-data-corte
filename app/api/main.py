from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import settings
from app.services.comparador_service import ComparadorService
from app.services.notificacao.smtp import EmailSMTPNotificador
from app.services.orchestrator import ColetaOrchestrator
from app.storage.file_storage import (
    FileDadosCorteRepository,
    FileEventoRepository,
    FileExecucaoRepository,
)

app = FastAPI(title="Pipeline Corte API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _build_orchestrator() -> ColetaOrchestrator:
    return ColetaOrchestrator(
        execucao_repo=FileExecucaoRepository(settings.STORAGE_PATH),
        dados_repo=FileDadosCorteRepository(settings.STORAGE_PATH),
        evento_repo=FileEventoRepository(settings.STORAGE_PATH),
        comparador=ComparadorService(),
        notificador=EmailSMTPNotificador(
            host=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            user=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=settings.SMTP_USE_TLS,
        ),
        destinatarios=settings.NOTIFICACAO_DESTINATARIOS,
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/coletas/{processadora}/executar")
def executar_coleta(processadora: str) -> dict:
    try:
        execucao = _build_orchestrator().executar(processadora)
        return {
            "id": execucao.id,
            "processadora": execucao.processadora,
            "status": execucao.status,
            "executada_em": execucao.executada_em,
            "total_convenios": execucao.total_convenios,
            "success_count": execucao.success_count,
            "error_count": execucao.error_count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/coletas/{processadora}/execucoes")
def listar_execucoes(processadora: str) -> list[dict]:
    repo = FileExecucaoRepository(settings.STORAGE_PATH)
    return [e.__dict__ for e in repo.listar(processadora)]


@app.get("/coletas/{processadora}/dados")
def obter_dados_atuais(processadora: str) -> list[dict]:
    execucao_repo = FileExecucaoRepository(settings.STORAGE_PATH)
    dados_repo = FileDadosCorteRepository(settings.STORAGE_PATH)
    ultima = execucao_repo.buscar_ultima_ok(processadora)
    if not ultima:
        return []
    return [d.__dict__ for d in dados_repo.buscar_por_execucao(ultima.id)]
