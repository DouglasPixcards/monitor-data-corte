"""Testa autenticação SafeConsig para qualquer perfil configurado no .env.

Uso:
    python scripts/test_safeconsig_auth.py
    python scripts/test_safeconsig_auth.py --env-key SAFECONSIG_HML
    python scripts/test_safeconsig_auth.py --env-key SAFECONSIG_PROD_SAOJOAODOSPATOS

Requer no .env as variáveis do perfil escolhido:
    {ENV_KEY}_BASE_URL
    {ENV_KEY}_ID_CONVENIO
    {ENV_KEY}_USERNAME
    {ENV_KEY}_PASSWORD
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

from dotenv import load_dotenv
load_dotenv()

from app.integrations.processors.base.exceptions import IntegrationError
from app.integrations.processors.safeconsig.client import SafeConsigClient
from app.integrations.processors.safeconsig.config import SafeConsigConfig


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Testa autenticação SafeConsig.")
    parser.add_argument(
        "--env-key",
        default="SAFECONSIG_HML",
        metavar="KEY",
        help="Prefixo das variáveis de ambiente (default: SAFECONSIG_HML)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    try:
        config = SafeConsigConfig.from_env(args.env_key)
    except IntegrationError as exc:
        print(f"[ERRO] Configuração inválida para {args.env_key!r}: {exc}", file=sys.stderr)
        return 1

    client = SafeConsigClient(config)
    try:
        client.autenticar()
    except IntegrationError as exc:
        print(f"[ERRO] Falha na autenticação ({args.env_key}): {exc}", file=sys.stderr)
        return 1

    print(f"✓ Autenticação SafeConsig bem-sucedida. (perfil: {args.env_key})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
