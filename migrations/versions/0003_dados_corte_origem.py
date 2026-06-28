"""dados_corte: coluna origem (scraper|api_estimativa|manual)

Revision ID: 0003_dados_corte_origem
Revises: 0002_evento_falha_campos
Create Date: 2026-06-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_dados_corte_origem"
down_revision: Union[str, None] = "0002_evento_falha_campos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("dados_corte", sa.Column("origem", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("dados_corte", "origem")
