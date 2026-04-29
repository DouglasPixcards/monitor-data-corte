from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Execucao:
    id: str
    processadora: str
    executada_em: str
    status: str
    total_convenios: int
    success_count: int
    error_count: int


@dataclass
class DadoCorte:
    id: str
    execucao_id: str
    convenio_key: str
    convenio_nome: str | None
    folha: str | None
    mes_atual: str | None
    data_corte: str | None
    coletado_em: str


@dataclass
class Evento:
    id: str
    tipo: str
    processadora: str
    convenio_key: str
    execucao_id: str
    detectado_em: str
    folha: str | None
    mes_atual: str | None
    data_corte_anterior: str | None
    data_corte_nova: str | None
