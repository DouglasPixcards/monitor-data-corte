"""schema inicial: execucoes, dados_corte, eventos

Revision ID: 0001_inicial
Revises:
Create Date: 2026-06-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_inicial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "execucoes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("processadora", sa.String(), nullable=False),
        sa.Column("executada_em", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("total_convenios", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("erros", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_execucoes_proc_data", "execucoes", ["processadora", "executada_em"])

    op.create_table(
        "dados_corte",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("execucao_id", sa.String(), nullable=False),
        sa.Column("convenio_key", sa.String(), nullable=False),
        sa.Column("coletado_em", sa.String(), nullable=False),
        sa.Column("convenio_nome", sa.String(), nullable=True),
        sa.Column("folha", sa.String(), nullable=True),
        sa.Column("mes_atual", sa.String(), nullable=True),
        sa.Column("data_corte", sa.String(), nullable=True),
    )
    op.create_index("ix_dados_corte_execucao_id", "dados_corte", ["execucao_id"])

    op.create_table(
        "eventos",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("processadora", sa.String(), nullable=False),
        sa.Column("convenio_key", sa.String(), nullable=False),
        sa.Column("execucao_id", sa.String(), nullable=False),
        sa.Column("detectado_em", sa.String(), nullable=False),
        sa.Column("folha", sa.String(), nullable=True),
        sa.Column("mes_atual", sa.String(), nullable=True),
        sa.Column("data_corte_anterior", sa.String(), nullable=True),
        sa.Column("data_corte_nova", sa.String(), nullable=True),
    )
    op.create_index("ix_eventos_proc_data", "eventos", ["processadora", "detectado_em"])


def downgrade() -> None:
    op.drop_index("ix_eventos_proc_data", table_name="eventos")
    op.drop_table("eventos")
    op.drop_index("ix_dados_corte_execucao_id", table_name="dados_corte")
    op.drop_table("dados_corte")
    op.drop_index("ix_execucoes_proc_data", table_name="execucoes")
    op.drop_table("execucoes")
