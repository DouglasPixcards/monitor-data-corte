"""Ponto único de montagem dos repositórios e do ColetaOrchestrator.

Concentra o switch STORAGE_BACKEND (file|postgres) e a composição do
orchestrator, eliminando a antiga duplicação de `_build_orchestrator()` que
existia em run_daily_collection.py, app/api/main.py e app/runner.py.
"""
from __future__ import annotations

from app.core.settings import settings
from app.services.comparador_service import ComparadorService
from app.services.notification.smtp import EmailSMTPNotificador
from app.services.orchestrator import ColetaOrchestrator
from app.storage.repository import (
    DadosCorteRepository,
    EventoRepository,
    ExecucaoRepository,
)


def build_repositories() -> tuple[ExecucaoRepository, DadosCorteRepository, EventoRepository]:
    """Retorna os 3 repositórios conforme STORAGE_BACKEND."""
    backend = settings.STORAGE_BACKEND.strip().lower()

    if backend == "postgres":
        from app.storage.postgres_storage import (
            PostgresDadosCorteRepository,
            PostgresEventoRepository,
            PostgresExecucaoRepository,
        )
        return (
            PostgresExecucaoRepository(),
            PostgresDadosCorteRepository(),
            PostgresEventoRepository(),
        )

    if backend != "file":
        raise ValueError(
            f"STORAGE_BACKEND inválido: {settings.STORAGE_BACKEND!r}. Use 'file' ou 'postgres'."
        )

    from app.storage.file_storage import (
        FileDadosCorteRepository,
        FileEventoRepository,
        FileExecucaoRepository,
    )
    return (
        FileExecucaoRepository(settings.STORAGE_PATH),
        FileDadosCorteRepository(settings.STORAGE_PATH),
        FileEventoRepository(settings.STORAGE_PATH),
    )


def build_orchestrator() -> ColetaOrchestrator:
    """Monta o ColetaOrchestrator com o backend de storage configurado."""
    execucao_repo, dados_repo, evento_repo = build_repositories()
    return ColetaOrchestrator(
        execucao_repo=execucao_repo,
        dados_repo=dados_repo,
        evento_repo=evento_repo,
        comparador=ComparadorService(),
        notificador=EmailSMTPNotificador(
            host=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            user=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=settings.SMTP_USE_TLS,
        ),
        destinatarios=settings.notification_DESTINATARIOS,
    )
