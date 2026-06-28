from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.models import Execucao, DadoCorte, Evento


class ExecucaoRepository(ABC):
    @abstractmethod
    def salvar(self, execucao: Execucao) -> None: ...

    @abstractmethod
    def buscar_ultima_ok(self, processadora: str) -> Execucao | None: ...

    @abstractmethod
    def buscar_ultima(self, processadora: str) -> Execucao | None:
        """Última execução REAL anterior (qualquer status, inclusive 'erro').

        Baseline para transição de STATUS por convênio (falha_nova/persistente/
        recuperado/gap). Difere de ``buscar_ultima_ok``, que ignora execuções
        totalmente 'erro' e serve de baseline para mudança de DADO."""
        ...

    @abstractmethod
    def listar(self, processadora: str) -> list[Execucao]: ...


class DadosCorteRepository(ABC):
    @abstractmethod
    def salvar_lote(self, dados: list[DadoCorte]) -> None: ...

    @abstractmethod
    def buscar_por_execucao(self, execucao_id: str) -> list[DadoCorte]: ...


class EventoRepository(ABC):
    @abstractmethod
    def salvar_lote(self, eventos: list[Evento]) -> None: ...

    @abstractmethod
    def listar(self, processadora: str, dias: int = 30, convenio_key: str | None = None) -> list[Evento]:
        """Eventos da processadora nos últimos `dias`. Se `convenio_key` for dado,
        filtra só os daquele convênio (base do histórico por-convênio)."""
        ...
