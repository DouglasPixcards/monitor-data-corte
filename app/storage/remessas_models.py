"""Tabelas do módulo de remessas (multiusuário) — Postgres-only.

Diferente das tabelas do coletor (`sql_models.py`, texto-ISO por paridade com o file
storage), aqui usamos tipos NATIVOS (DATE/TIMESTAMPTZ/NUMERIC/BOOLEAN): o módulo não tem
backend file, e as datas nativas alimentam a sugestão banksoft (−7d) e o lead time.

IMPORTANTE: adicionar modelos aqui em LOCKSTEP com a migration correspondente —
o `alembic check` do CI compara metadata × migrations.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func, text
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
