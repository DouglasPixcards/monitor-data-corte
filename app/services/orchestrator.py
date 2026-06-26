from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from app.core.models import DadoCorte, Evento, Execucao
from app.services.comparador_service import ComparadorService
from app.services.notification.base import NotificadorBase
from app.services.notification.digest_builder import DigestBuilder
from app.services.storage_helpers import now_iso
from app.storage.repository import (
    DadosCorteRepository,
    EventoRepository,
    ExecucaoRepository,
)

logger = logging.getLogger(__name__)


@dataclass
class ResultadoColeta:
    """Bundle de uma coleta de processadora — insumo do digest (agregado ou não)."""
    processadora: str
    execucao: Execucao
    eventos: list[Evento] = field(default_factory=list)
    resultado_lote: dict = field(default_factory=dict)


def executar_coleta_lote(processadora: str, convenio_filter: str | None = None) -> dict:
    """Thin wrapper that defers the scraper import to call time.

    Having this name at module level allows tests to patch
    ``app.services.orchestrator.executar_coleta_lote`` without importing
    the scraper chain (Playwright / file_storage) at collection time.
    """
    from app.services.coleta_service import executar_coleta_lote as _real  # noqa: PLC0415

    return _real(processadora, convenio_filter=convenio_filter)


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

    # ------------------------------------------------------------------
    # Coleta (sem notificar) — base de tudo
    # ------------------------------------------------------------------

    def coletar(self, processadora: str, convenio_filter: str | None = None) -> ResultadoColeta:
        """Roda a coleta, persiste execução/dados/eventos e devolve o bundle.

        NÃO envia e-mail — a notificação fica a cargo de ``executar`` (1
        processadora) ou ``notificar_agregado``/``executar_todas`` (resumo único).
        """
        # 1a. Baseline de DADOS = última ok/partial (ignora execuções 100% erro).
        ultima_ok = self._execucao_repo.buscar_ultima_ok(processadora)
        dados_anteriores = (
            self._dados_repo.buscar_por_execucao(ultima_ok.id) if ultima_ok else []
        )

        # 1b. Baseline de STATUS = última execução REAL anterior (qualquer status).
        status_anterior = self._montar_status_anterior(processadora)

        # 2. Rodar scrapers/coletores.
        resultado_lote = executar_coleta_lote(processadora, convenio_filter=convenio_filter)

        # Status EFETIVO por convênio: "ok" só se veio data de corte; "sem_dado"
        # quando coletou mas não retornou data; "erro" quando falhou.
        convs_com_dado = {
            r["convenio_key"]
            for r in resultado_lote.get("records", [])
            if r.get("data_corte") not in (None, "")
        }
        status_atual: dict[str, dict] = {}
        for c in resultado_lote.get("convenios", []):
            ck = c["convenio_key"]
            if c.get("status") != "ok":
                efetivo = "erro"
            elif ck in convs_com_dado:
                efetivo = "ok"
            else:
                efetivo = "sem_dado"
            status_atual[ck] = {
                "status": efetivo,
                "erro": c.get("erro"),
                "records_count": c.get("records_count", 0),
                "known_failure": bool(c.get("known_failure")),
                "convenio_nome": c.get("convenio_nome"),
            }
        # Numa rodada filtrada (1 convênio) não dá pra inferir gap das outras.
        if convenio_filter:
            status_anterior = {k: v for k, v in status_anterior.items() if k in status_atual}

        # 3. Salvar execução (erros por convênio extraídos do resultado do lote).
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

        # 4. Converter e salvar dados coletados com sucesso.
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

        # 5. Comparar (dados + status) e persistir eventos.
        eventos = self._comparador.comparar(
            processadora=processadora,
            execucao_id=execucao.id,
            anteriores=dados_anteriores,
            atuais=dados_atuais,
            status_anterior=status_anterior,
            status_atual=status_atual,
        )
        self._evento_repo.salvar_lote(eventos)

        return ResultadoColeta(processadora=processadora, execucao=execucao,
                               eventos=eventos, resultado_lote=resultado_lote)

    # ------------------------------------------------------------------
    # Notificação
    # ------------------------------------------------------------------

    def executar(self, processadora: str, convenio_filter: str | None = None) -> Execucao:
        """Coleta UMA processadora e envia o resumo dela (uso on-demand/API)."""
        res = self.coletar(processadora, convenio_filter=convenio_filter)
        if self._destinatarios:
            assunto, corpo = DigestBuilder.build(processadora, res.eventos, res.resultado_lote)
            try:
                self._notificador.enviar(assunto, self._destinatarios, corpo)
            except Exception:
                logger.exception("Falha ao enviar notificação por e-mail")
        return res.execucao

    def notificar_agregado(self, resultados: list[ResultadoColeta]) -> None:
        """Envia UM único e-mail consolidando todas as processadoras da rodada."""
        if not self._destinatarios or not resultados:
            return
        assunto, corpo = DigestBuilder.build_agregado(resultados)
        try:
            self._notificador.enviar(assunto, self._destinatarios, corpo)
        except Exception:
            logger.exception("Falha ao enviar resumo diário agregado por e-mail")

    def executar_todas(self, processadoras: list[str]) -> list[ResultadoColeta]:
        """Coleta todas as processadoras (sem retry) e envia UM e-mail consolidado."""
        resultados: list[ResultadoColeta] = []
        for processadora in processadoras:
            try:
                resultados.append(self.coletar(processadora))
            except Exception:
                logger.exception("Falha ao coletar processadora %s", processadora)
        self.notificar_agregado(resultados)
        return resultados

    # ------------------------------------------------------------------
    # Baseline de status
    # ------------------------------------------------------------------

    def _montar_status_anterior(self, processadora: str) -> dict[str, str]:
        """Status por convênio na última execução real (baseline de status).

        "coletado" se teve DadoCorte com data de corte; "sem_dado" se teve
        DadoCorte mas sem valor; "falhou" se constou em Execucao.erros.
        Um valor presente tem precedência (coletado > sem_dado).
        """
        ultima = self._execucao_repo.buscar_ultima(processadora)
        if ultima is None:
            return {}
        status: dict[str, str] = {}
        for d in self._dados_repo.buscar_por_execucao(ultima.id):
            if status.get(d.convenio_key) == "coletado":
                continue
            status[d.convenio_key] = "coletado" if d.data_corte not in (None, "") else "sem_dado"
        for err in (ultima.erros or []):
            ck = err.get("convenio_key")
            if ck and ck not in status:
                status[ck] = "falhou"
        return status
