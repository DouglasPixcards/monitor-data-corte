from __future__ import annotations

import logging
from dataclasses import asdict

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

logger = logging.getLogger(__name__)

app = FastAPI(title="Pipeline Corte API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _check_smtp_config() -> None:
    if not settings.SMTP_HOST:
        logger.warning("SMTP_HOST não configurado — notificações por e-mail desabilitadas")


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


@app.post("/notificacao/testar")
def testar_smtp() -> dict:
    if not settings.SMTP_HOST:
        raise HTTPException(status_code=422, detail="SMTP_HOST não configurado.")
    if not settings.NOTIFICACAO_DESTINATARIOS:
        raise HTTPException(status_code=422, detail="NOTIFICACAO_DESTINATARIOS não configurado.")
    notificador = EmailSMTPNotificador(
        host=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        user=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        use_tls=settings.SMTP_USE_TLS,
    )
    try:
        notificador.enviar(
            assunto="[Teste] Monitor Datas de Corte — verificação de SMTP",
            destinatarios=settings.NOTIFICACAO_DESTINATARIOS,
            corpo_html="<p>Configuração SMTP funcionando corretamente.</p>",
        )
    except Exception:
        logger.exception("Falha no teste de envio SMTP")
        raise HTTPException(status_code=500, detail="Falha ao enviar e-mail de teste.")
    return {"status": "ok", "destinatarios": settings.NOTIFICACAO_DESTINATARIOS}


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
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        logger.exception("Falha ao executar coleta para %s", processadora)
        raise HTTPException(status_code=500, detail="Falha interna ao executar coleta.")


@app.get("/coletas/{processadora}/execucoes")
def listar_execucoes(processadora: str) -> list[dict]:
    repo = FileExecucaoRepository(settings.STORAGE_PATH)
    return [asdict(e) for e in repo.listar(processadora)]


@app.get("/coletas/{processadora}/dados")
def obter_dados_atuais(processadora: str) -> list[dict]:
    execucao_repo = FileExecucaoRepository(settings.STORAGE_PATH)
    dados_repo = FileDadosCorteRepository(settings.STORAGE_PATH)
    ultima = execucao_repo.buscar_ultima_ok(processadora)
    if not ultima:
        return []
    return [asdict(d) for d in dados_repo.buscar_por_execucao(ultima.id)]
