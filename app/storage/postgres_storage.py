"""Backend PostgreSQL — implementa as 3 interfaces de `repository.py`.

Drop-in para os `File*Repository`: mesmas assinaturas e MESMOS comportamentos
observáveis (ver `file_storage.py`):
  - Execucao: insere; `buscar_ultima_ok` filtra ok/partial_success; ordena DESC.
  - DadoCorte: `salvar_lote` é fail-fast se o execucao_id já tem dados.
  - Evento: `salvar_lote` é append puro; `listar` cobre os últimos N dias, DESC.
"""
from __future__ import annotations

from datetime import date, timedelta
from enum import Enum

from sqlalchemy import select

from app.core.enums import CollectionStatus
from app.core.models import DadoCorte, Evento, Execucao
from app.storage.db import session_scope
from app.storage.repository import (
    DadosCorteRepository,
    EventoRepository,
    ExecucaoRepository,
)
from app.storage.sql_models import DadoCorteRow, EventoRow, ExecucaoRow


def _tipo_str(tipo) -> str:
    """Normaliza EventoTipo (str-Enum) ou string crua para o valor textual."""
    return tipo.value if isinstance(tipo, Enum) else str(tipo)


class PostgresExecucaoRepository(ExecucaoRepository):
    def salvar(self, execucao: Execucao) -> None:
        with session_scope() as s:
            s.add(ExecucaoRow(
                id=execucao.id,
                processadora=execucao.processadora,
                executada_em=execucao.executada_em,
                status=execucao.status,
                total_convenios=execucao.total_convenios,
                success_count=execucao.success_count,
                error_count=execucao.error_count,
                erros=execucao.erros or [],
            ))

    def listar(self, processadora: str) -> list[Execucao]:
        with session_scope() as s:
            rows = s.execute(
                select(ExecucaoRow)
                .where(ExecucaoRow.processadora == processadora)
                .order_by(ExecucaoRow.executada_em.desc())
            ).scalars().all()
            return [self._to_model(r) for r in rows]

    def buscar_ultima_ok(self, processadora: str) -> Execucao | None:
        ok_status = [CollectionStatus.OK.value, CollectionStatus.PARTIAL_SUCCESS.value]
        with session_scope() as s:
            row = s.execute(
                select(ExecucaoRow)
                .where(
                    ExecucaoRow.processadora == processadora,
                    ExecucaoRow.status.in_(ok_status),
                )
                .order_by(ExecucaoRow.executada_em.desc())
                .limit(1)
            ).scalars().first()
            return self._to_model(row) if row else None

    def buscar_ultima(self, processadora: str) -> Execucao | None:
        with session_scope() as s:
            row = s.execute(
                select(ExecucaoRow)
                .where(ExecucaoRow.processadora == processadora)
                .order_by(ExecucaoRow.executada_em.desc())
                .limit(1)
            ).scalars().first()
            return self._to_model(row) if row else None

    @staticmethod
    def _to_model(row: ExecucaoRow) -> Execucao:
        return Execucao(
            id=row.id,
            processadora=row.processadora,
            executada_em=row.executada_em,
            status=row.status,
            total_convenios=row.total_convenios,
            success_count=row.success_count,
            error_count=row.error_count,
            erros=row.erros or [],
        )


class PostgresDadosCorteRepository(DadosCorteRepository):
    def salvar_lote(self, dados: list[DadoCorte]) -> None:
        if not dados:
            return
        execucao_ids = {d.execucao_id for d in dados}
        with session_scope() as s:
            # Fail-fast: espelha o FileExistsError do file storage.
            existentes = s.execute(
                select(DadoCorteRow.execucao_id)
                .where(DadoCorteRow.execucao_id.in_(execucao_ids))
                .distinct()
            ).scalars().all()
            if existentes:
                raise FileExistsError(
                    f"Dados de corte já registrados para execucao_id={existentes[0]}"
                )
            s.add_all([
                DadoCorteRow(
                    id=d.id,
                    execucao_id=d.execucao_id,
                    convenio_key=d.convenio_key,
                    coletado_em=d.coletado_em,
                    convenio_nome=d.convenio_nome,
                    folha=d.folha,
                    mes_atual=d.mes_atual,
                    data_corte=d.data_corte,
                )
                for d in dados
            ])

    def buscar_por_execucao(self, execucao_id: str) -> list[DadoCorte]:
        with session_scope() as s:
            rows = s.execute(
                select(DadoCorteRow)
                .where(DadoCorteRow.execucao_id == execucao_id)
                .order_by(DadoCorteRow.convenio_key, DadoCorteRow.id)
            ).scalars().all()
            return [self._to_model(r) for r in rows]

    @staticmethod
    def _to_model(row: DadoCorteRow) -> DadoCorte:
        return DadoCorte(
            id=row.id,
            execucao_id=row.execucao_id,
            convenio_key=row.convenio_key,
            coletado_em=row.coletado_em,
            convenio_nome=row.convenio_nome,
            folha=row.folha,
            mes_atual=row.mes_atual,
            data_corte=row.data_corte,
        )


class PostgresEventoRepository(EventoRepository):
    def salvar_lote(self, eventos: list[Evento]) -> None:
        if not eventos:
            return
        with session_scope() as s:
            s.add_all([
                EventoRow(
                    id=e.id,
                    tipo=_tipo_str(e.tipo),
                    processadora=e.processadora,
                    convenio_key=e.convenio_key,
                    execucao_id=e.execucao_id,
                    detectado_em=e.detectado_em,
                    folha=e.folha,
                    mes_atual=e.mes_atual,
                    data_corte_anterior=e.data_corte_anterior,
                    data_corte_nova=e.data_corte_nova,
                    categoria=getattr(e, "categoria", None),
                    subtipo=getattr(e, "subtipo", None),
                    detalhe=getattr(e, "detalhe", None),
                )
                for e in eventos
            ])

    def listar(self, processadora: str, dias: int = 30) -> list[Evento]:
        # Cobre hoje e os (dias-1) dias anteriores — mesma janela do file storage.
        cutoff = str(date.today() - timedelta(days=dias - 1))
        with session_scope() as s:
            rows = s.execute(
                select(EventoRow)
                .where(
                    EventoRow.processadora == processadora,
                    EventoRow.detectado_em >= cutoff,
                )
                .order_by(EventoRow.detectado_em.desc())
            ).scalars().all()
            return [self._to_model(r) for r in rows]

    @staticmethod
    def _to_model(row: EventoRow) -> Evento:
        return Evento(
            id=row.id,
            tipo=row.tipo,
            processadora=row.processadora,
            convenio_key=row.convenio_key,
            execucao_id=row.execucao_id,
            detectado_em=row.detectado_em,
            folha=row.folha,
            mes_atual=row.mes_atual,
            data_corte_anterior=row.data_corte_anterior,
            data_corte_nova=row.data_corte_nova,
            categoria=row.categoria,
            subtipo=row.subtipo,
            detalhe=row.detalhe,
        )
