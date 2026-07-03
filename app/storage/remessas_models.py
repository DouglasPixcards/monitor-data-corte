"""Tabelas do módulo de remessas (multiusuário) — Postgres-only.

Diferente das tabelas do coletor (`sql_models.py`, texto-ISO por paridade com o file
storage), aqui usamos tipos NATIVOS (DATE/TIMESTAMPTZ/NUMERIC/BOOLEAN): o módulo não tem
backend file, e as datas nativas alimentam a sugestão banksoft (−7d) e o lead time.

IMPORTANTE: adicionar modelos aqui em LOCKSTEP com a migration correspondente —
o `alembic check` do CI compara metadata × migrations.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.sql_models import Base


class UsuarioRow(Base):
    __tablename__ = "usuarios"

    id: Mapped[str] = mapped_column(String, primary_key=True)          # uuid4 str
    # SEMPRE normalizado para lowercase na aplicação (auth_service) — o UNIQUE se apoia nisso.
    username: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)  # bcrypt
    role: Mapped[str] = mapped_column(String, nullable=False)          # admin|operacoes|conciliacao
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SessaoRow(Base):
    __tablename__ = "sessoes"

    # sha256 hex do token opaco do cookie — o token em si nunca é armazenado.
    token_hash: Mapped[str] = mapped_column(String, primary_key=True)
    usuario_id: Mapped[str] = mapped_column(
        String, ForeignKey("usuarios.id"), nullable=False, index=True
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revogada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConvenioRegistroRow(Base):
    """Cadastro de convênios da planilha — MAIOR que o conjunto monitorado.
    `monitor_key` (nullable, UNIQUE = 1:1 estrito) liga ao convênio do monitor."""

    __tablename__ = "convenios_registro"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    cod_empr: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    link_portal: Mapped[str | None] = mapped_column(String, nullable=True)
    tipo_desconto: Mapped[str] = mapped_column(String, nullable=False)  # automatico|remessa
    prod_credito: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    prod_beneficio: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    prod_compras: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    monitor_key: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CicloRemessaRow(Base):
    """Uma linha da planilha: o ciclo de remessa de um convênio numa competência."""

    __tablename__ = "ciclos_remessa"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    registro_id: Mapped[str] = mapped_column(
        String, ForeignKey("convenios_registro.id"), nullable=False
    )
    competencia: Mapped[str] = mapped_column(String, nullable=False)        # "MM/YYYY"
    competencia_inicio: Mapped[date] = mapped_column(Date, nullable=False)  # dia 1 (ordenável)

    # data_site = SNAPSHOT do valor do monitor (sync) ou input manual (não-monitorados).
    data_site: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_site_origem: Mapped[str | None] = mapped_column(String, nullable=True)  # monitor|manual
    data_site_anterior: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_site_alterada: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    data_site_atualizada_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Campos da Conciliação
    data_envio: Mapped[date | None] = mapped_column(Date, nullable=True)
    valor_enviado: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    qtd_contratos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    credito_valor: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    credito_qtd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    beneficio_valor: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    beneficio_qtd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    compras_valor: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    compras_qtd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    validado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    # Campo da Operações
    corte_banksoft: Mapped[date | None] = mapped_column(Date, nullable=True)

    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("registro_id", "competencia", name="ux_ciclo_registro_competencia"),
        Index("ix_ciclos_competencia_inicio", "competencia_inicio"),
    )


class RemessaAuditoriaRow(Base):
    """Log imutável (append-only): quem mudou o quê, quando, de → para."""

    __tablename__ = "remessa_auditoria"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    entidade: Mapped[str] = mapped_column(String, nullable=False)      # ciclo|registro|usuario
    entidade_id: Mapped[str] = mapped_column(String, nullable=False)
    acao: Mapped[str] = mapped_column(String, nullable=False)          # create|update|sync
    campo: Mapped[str | None] = mapped_column(String, nullable=True)
    valor_anterior: Mapped[str | None] = mapped_column(Text, nullable=True)
    valor_novo: Mapped[str | None] = mapped_column(Text, nullable=True)
    usuario_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("usuarios.id"), nullable=True   # NULL = sistema (sync/seed)
    )
    usuario_nome: Mapped[str] = mapped_column(String, nullable=False)  # snapshot do display name
    ocorrido_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_auditoria_entidade", "entidade", "entidade_id", "ocorrido_em"),
    )
