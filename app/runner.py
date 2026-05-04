# from app.services.collector_service import executar_coleta
from __future__ import annotations

from app.core.settings import settings
from app.services.comparador_service import ComparadorService
from app.services.notification.smtp import EmailSMTPNotificador
from app.services.orchestrator import ColetaOrchestrator
from app.storage.file_storage import (
    FileDadosCorteRepository,
    FileEventoRepository,
    FileExecucaoRepository,
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
        destinatarios=settings.notification_DESTINATARIOS,
    )

def run() -> None:
    # processadora = "consigup"
    # executar_coleta(processadora)

    try:
        execucao = _build_orchestrator().executar("consigfacil")
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