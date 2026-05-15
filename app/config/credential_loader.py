"""Carrega credenciais de variáveis de ambiente.

Convenção de nomes:
    {PORTAL}_{CONVENIO_KEY}_USERNAME
    {PORTAL}_{CONVENIO_KEY}_PASSWORD

Exemplo:
    CONSIGNET_MARINGA_USERNAME
    CONSIGNET_MARINGA_PASSWORD

Nenhum valor é impresso em log ou exposto em exceção.
"""
from __future__ import annotations

import os


def load_credentials(portal: str, convenio_key: str) -> tuple[str, str]:
    """Retorna (username, password) para o par portal+convenio.

    Levanta CredentialNotFoundError se alguma variável estiver ausente.
    """
    prefix = f"{portal.upper()}_{convenio_key.upper()}"
    username_var = f"{prefix}_USERNAME"
    password_var = f"{prefix}_PASSWORD"

    username = os.getenv(username_var)
    password = os.getenv(password_var)

    if not username:
        raise CredentialNotFoundError(
            f"Variável de ambiente ausente ou vazia: {username_var}"
        )
    if not password:
        raise CredentialNotFoundError(
            f"Variável de ambiente ausente ou vazia: {password_var}"
        )

    return username, password


def credentials_exist(portal: str, convenio_key: str) -> bool:
    prefix = f"{portal.upper()}_{convenio_key.upper()}"
    return bool(os.getenv(f"{prefix}_USERNAME")) and bool(os.getenv(f"{prefix}_PASSWORD"))


class CredentialNotFoundError(Exception):
    pass
