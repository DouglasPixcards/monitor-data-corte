"""Tabelas SQLAlchemy do backend PostgreSQL.

Mantidas SEPARADAS das dataclasses de domínio (`app/core/models.py`) para não
acoplar o domínio ao ORM. Os repositórios Postgres convertem entre as duas.

Datas (`executada_em`, `coletado_em`, `detectado_em`) são guardadas como texto
ISO 8601 — exatamente como no file storage. Strings ISO ordenam
lexicograficamente = cronologicamente, então `ORDER BY ... DESC` e os filtros
por janela de dias funcionam por comparação textual, sem parsing de timezone.
"""
from __future__ import annotations

from sqlalchemy import Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ExecucaoRow(Base):
    __tablename__ = "execucoes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    processadora: Mapped[str] = mapped_column(String, nullable=False)
    executada_em: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    total_convenios: Mapped[int] = mapped_column(Integer, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False)
    erros: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    __table_args__ = (
        Index("ix_execucoes_proc_data", "processadora", "executada_em"),
    )


class DadoCorteRow(Base):
    __tablename__ = "dados_corte"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    execucao_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    convenio_key: Mapped[str] = mapped_column(String, nullable=False)
    coletado_em: Mapped[str] = mapped_column(String, nullable=False)
    convenio_nome: Mapped[str | None] = mapped_column(String, nullable=True)
    folha: Mapped[str | None] = mapped_column(String, nullable=True)
    mes_atual: Mapped[str | None] = mapped_column(String, nullable=True)
    data_corte: Mapped[str | None] = mapped_column(String, nullable=True)
    # Sem UNIQUE composto: um convênio tem MÚLTIPLAS folhas/órgãos por execução
    # (ex.: "Cuiabá Prev" + "Prefeitura de Cuiabá" sob convenio_key=cuiaba), e o
    # corpus real nem (execucao_id, convenio_key, folha) é único — só o id (PK).
    # O guard de re-coleta é por execucao_id (fail-fast na aplicação).


class EventoRow(Base):
    __tablename__ = "eventos"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tipo: Mapped[str] = mapped_column(String, nullable=False)
    processadora: Mapped[str] = mapped_column(String, nullable=False)
    convenio_key: Mapped[str] = mapped_column(String, nullable=False)
    execucao_id: Mapped[str] = mapped_column(String, nullable=False)
    detectado_em: Mapped[str] = mapped_column(String, nullable=False)
    folha: Mapped[str | None] = mapped_column(String, nullable=True)
    mes_atual: Mapped[str | None] = mapped_column(String, nullable=True)
    data_corte_anterior: Mapped[str | None] = mapped_column(String, nullable=True)
    data_corte_nova: Mapped[str | None] = mapped_column(String, nullable=True)
    categoria: Mapped[str | None] = mapped_column(String, nullable=True)
    subtipo: Mapped[str | None] = mapped_column(String, nullable=True)
    detalhe: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        Index("ix_eventos_proc_data", "processadora", "detectado_em"),
    )
