"""Cria o PRIMEIRO usuário admin do módulo de remessas (bootstrap).

Recusa rodar se já existir qualquer admin — depois do bootstrap, usuários são
gerenciados pelo painel. A senha vem de --password ou da env ADMIN_SEED_PASSWORD
(nunca é logada).

Uso:
    python scripts/seed_admin_user.py --username admin --display-name "Admin"
    (com STORAGE_BACKEND=postgres e DATABASE_URL configurados; migrations na head)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.services import auth_service  # noqa: E402
from app.storage import db  # noqa: E402
from app.storage.remessas_models import UsuarioRow  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--password", default=None,
                        help="Senha (ou use a env ADMIN_SEED_PASSWORD)")
    args = parser.parse_args()

    senha = args.password or os.getenv("ADMIN_SEED_PASSWORD")
    if not senha:
        print("ERRO: informe --password ou a env ADMIN_SEED_PASSWORD.")
        return 1
    if len(senha) < 8:
        print("ERRO: senha precisa de ao menos 8 caracteres.")
        return 1
    if len(senha.encode("utf-8")) > 72:
        print("ERRO: senha excede 72 bytes (limite do bcrypt).")
        return 1

    db.assert_ready()  # falha claro se o Postgres/migrations não estão prontos

    with db.session_scope() as session:
        # Só admins ATIVOS bloqueiam o bootstrap (um admin desativado não pode
        # impedir a recuperação do sistema).
        ja_existe = session.execute(
            select(UsuarioRow).where(UsuarioRow.role == "admin",
                                     UsuarioRow.ativo.is_(True))
        ).scalars().first()
        if ja_existe is not None:
            print(f"ERRO: já existe um admin ({ja_existe.username}) — "
                  "gerencie usuários pelo painel.")
            return 1
        usuario = auth_service.criar_usuario(
            session, args.username, args.display_name, senha, "admin")
        session.flush()
        print(f"✓ Admin criado: {usuario.username} (id {usuario.id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
