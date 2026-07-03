"""convenios_registro + ciclos_remessa + remessa_auditoria — módulo de remessas

Revision ID: 0005_remessas
Revises: 0004_usuarios_sessoes
Create Date: 2026-06-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_remessas"
down_revision: Union[str, None] = "0004_usuarios_sessoes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "convenios_registro",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("cod_empr", sa.Integer(), nullable=False, unique=True),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("link_portal", sa.String(), nullable=True),
        sa.Column("tipo_desconto", sa.String(), nullable=False),
        sa.Column("prod_credito", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("prod_beneficio", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("prod_compras", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("monitor_key", sa.String(), nullable=True, unique=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )

    op.create_table(
        "ciclos_remessa",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("registro_id", sa.String(),
                  sa.ForeignKey("convenios_registro.id"), nullable=False),
        sa.Column("competencia", sa.String(), nullable=False),
        sa.Column("competencia_inicio", sa.Date(), nullable=False),
        sa.Column("data_site", sa.Date(), nullable=True),
        sa.Column("data_site_origem", sa.String(), nullable=True),
        sa.Column("data_site_anterior", sa.Date(), nullable=True),
        sa.Column("data_site_alterada", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("data_site_atualizada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_envio", sa.Date(), nullable=True),
        sa.Column("valor_enviado", sa.Numeric(14, 2), nullable=True),
        sa.Column("qtd_contratos", sa.Integer(), nullable=True),
        sa.Column("credito_valor", sa.Numeric(14, 2), nullable=True),
        sa.Column("credito_qtd", sa.Integer(), nullable=True),
        sa.Column("beneficio_valor", sa.Numeric(14, 2), nullable=True),
        sa.Column("beneficio_qtd", sa.Integer(), nullable=True),
        sa.Column("compras_valor", sa.Numeric(14, 2), nullable=True),
        sa.Column("compras_qtd", sa.Integer(), nullable=True),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("validado", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("corte_banksoft", sa.Date(), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("registro_id", "competencia",
                            name="ux_ciclo_registro_competencia"),
    )
    op.create_index("ix_ciclos_competencia_inicio", "ciclos_remessa", ["competencia_inicio"])

    op.create_table(
        "remessa_auditoria",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("entidade", sa.String(), nullable=False),
        sa.Column("entidade_id", sa.String(), nullable=False),
        sa.Column("acao", sa.String(), nullable=False),
        sa.Column("campo", sa.String(), nullable=True),
        sa.Column("valor_anterior", sa.Text(), nullable=True),
        sa.Column("valor_novo", sa.Text(), nullable=True),
        sa.Column("usuario_id", sa.String(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("usuario_nome", sa.String(), nullable=False),
        sa.Column("ocorrido_em", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_auditoria_entidade", "remessa_auditoria",
                    ["entidade", "entidade_id", "ocorrido_em"])


def downgrade() -> None:
    op.drop_index("ix_auditoria_entidade", table_name="remessa_auditoria")
    op.drop_table("remessa_auditoria")
    op.drop_index("ix_ciclos_competencia_inicio", table_name="ciclos_remessa")
    op.drop_table("ciclos_remessa")
    op.drop_table("convenios_registro")
