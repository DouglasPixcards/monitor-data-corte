from __future__ import annotations

from dataclasses import dataclass, field

from app.core.enums import EventoTipo


@dataclass
class Execucao:
    id: str
    processadora: str
    executada_em: str
    status: str
    total_convenios: int
    success_count: int
    error_count: int
    erros: list[dict] = field(default_factory=list)


@dataclass
class DadoCorte:
    id: str
    execucao_id: str
    convenio_key: str
    coletado_em: str
    convenio_nome: str | None = field(default=None)
    folha: str | None = field(default=None)
    mes_atual: str | None = field(default=None)
    data_corte: str | None = field(default=None)


@dataclass
class Evento:
    id: str
    tipo: EventoTipo
    processadora: str
    convenio_key: str
    execucao_id: str
    detectado_em: str
    folha: str | None = field(default=None)
    mes_atual: str | None = field(default=None)
    data_corte_anterior: str | None = field(default=None)
    data_corte_nova: str | None = field(default=None)