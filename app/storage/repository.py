from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.models import Execucao, DadoCorte, Evento


class ExecucaoRepository(ABC):
    @abstractmethod
    def salvar(self, execucao: Execucao) -> None: ...

    @abstractmethod
    def buscar_ultima_ok(self, processadora: str) -> Execucao | None: ...

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
