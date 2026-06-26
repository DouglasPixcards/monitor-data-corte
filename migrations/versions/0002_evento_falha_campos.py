"""eventos: campos de falha (categoria, subtipo, detalhe)

Revision ID: 0002_evento_falha_campos
Revises: 0001_inicial
Create Date: 2026-06-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_evento_falha_campos"
down_revision: Union[str, None] = "0001_inicial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("eventos", sa.Column("categoria", sa.String(), nullable=True))
    op.add_column("eventos", sa.Column("subtipo", sa.String(), nullable=True))
    op.add_column("eventos", sa.Column("detalhe", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("eventos", "detalhe")
    op.drop_column("eventos", "subtipo")
    op.drop_column("eventos", "categoria")
