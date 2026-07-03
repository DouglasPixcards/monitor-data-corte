"""usuarios + sessoes — auth do módulo de remessas

Revision ID: 0004_usuarios_sessoes
Revises: 0003_dados_corte_origem
Create Date: 2026-06-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_usuarios_sessoes"
down_revision: Union[str, None] = "0003_dados_corte_origem"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("username", sa.String(), nullable=False, unique=True),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_table(
        "sessoes",
        sa.Column("token_hash", sa.String(), primary_key=True),
        sa.Column("usuario_id", sa.String(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revogada_em", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_sessoes_usuario_id", "sessoes", ["usuario_id"])


def downgrade() -> None:
    op.drop_index("ix_sessoes_usuario_id", table_name="sessoes")
    op.drop_table("sessoes")
    op.drop_table("usuarios")
