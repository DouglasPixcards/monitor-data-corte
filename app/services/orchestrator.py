from __future__ import annotations

import logging
import uuid

from app.core.enums import EventoTipo

logger = logging.getLogger(__name__)
from app.core.models import DadoCorte, Execucao
from app.services.comparador_service import ComparadorService
from app.services.notification.base import NotificadorBase
from app.services.notification.digest_builder import DigestBuilder
from app.services.storage_helpers import now_iso
from app.storage.repository import (
    DadosCorteRepository,
    EventoRepository,
    ExecucaoRepository,
)


def executar_coleta_lote(processadora: str) -> dict:
    """Thin wrapper that defers the scraper import to call time.

    Having this name at module level allows tests to patch
    ``app.services.orchestrator.executar_coleta_lote`` without importing
    the scraper chain (Playwright / file_storage) at collection time.
    """
    from app.services.coleta_service import executar_coleta_lote as _real  # noqa: PLC0415

    return _real(processadora)


class ColetaOrchestrator:
    def __init__(
        self,
        execucao_repo: ExecucaoRepository,
        dados_repo: DadosCorteRepository,
        evento_repo: EventoRepository,
        comparador: ComparadorService,
        notificador: NotificadorBase,
        destinatarios: list[str],
    ) -> None:
        self._execucao_repo = execucao_repo
        self._dados_repo = dados_repo
        self._evento_repo = evento_repo
        self._comparador = comparador
        self._notificador = notificador
        self._destinatarios = destinatarios

    def executar(self, processadora: str) -> Execucao:
        # 1. Carregar dados anteriores ANTES de salvar qualquer coisa
        ultima_ok = self._execucao_repo.buscar_ultima_ok(processadora)
        dados_anteriores = (
            self._dados_repo.buscar_por_execucao(ultima_ok.id) if ultima_ok else []
        )

        # 2. Rodar scrapers
        resultado_lote = executar_coleta_lote(processadora)

        # 3. Salvar execução (erros por convênio extraídos do resultado do lote)
        erros_convenios = [
            {
                "convenio_key": c["convenio_key"],
                "convenio_nome": c.get("convenio_nome"),
                "status": c["status"],
                "erro": c.get("erro"),
            }
            for c in resultado_lote.get("convenios", [])
            if c.get("status") != "ok"
        ]
        execucao = Execucao(
            id=str(uuid.uuid4()),
            processadora=processadora,
            executada_em=now_iso(),
            status=resultado_lote["status"],
            total_convenios=resultado_lote["total_convenios"],
            success_count=resultado_lote["success_count"],
            error_count=resultado_lote["error_count"],
            erros=erros_convenios,
        )
        self._execucao_repo.salvar(execucao)

        # 4. Converter e salvar dados coletados com sucesso
        dados_atuais = [
            DadoCorte(
                id=str(uuid.uuid4()),
                execucao_id=execucao.id,
                convenio_key=r["convenio_key"],
                convenio_nome=r.get("convenio_nome"),
                folha=r.get("folha"),
                mes_atual=r.get("mes_atual"),
                data_corte=r.get("data_corte"),
                coletado_em=now_iso(),
            )
            for r in resultado_lote.get("records", [])
        ]
        self._dados_repo.salvar_lote(dados_atuais)

        # 5. Comparar e persistir eventos
        eventos = self._comparador.comparar(
            processadora=processadora,
            execucao_id=execucao.id,
            anteriores=dados_anteriores,
            atuais=dados_atuais,
        )
        self._evento_repo.salvar_lote(eventos)

        # 6. Notificar mudanças de data de corte
        mudancas = [e for e in eventos if e.tipo == EventoTipo.DATA_CORTE_ALTERADA]
        if mudancas and self._destinatarios:
            assunto, corpo = DigestBuilder.build(processadora, mudancas)
            try:
                self._notificador.enviar(assunto, self._destinatarios, corpo)
            except Exception:
                logger.exception("Falha ao enviar notificação por e-mail")

        return execucao