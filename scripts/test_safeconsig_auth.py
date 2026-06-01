"""Testa autenticação SafeConsig HML.

Requer no .env:
    SAFECONSIG_HML_BASE_URL
    SAFECONSIG_HML_ID_CONVENIO
    SAFECONSIG_HML_USERNAME
    SAFECONSIG_HML_PASSWORD

Uso:
    python scripts/test_safeconsig_auth.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Permite importar app.* a partir da raiz do projeto
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

from dotenv import load_dotenv
load_dotenv()

from app.integrations.processors.base.exceptions import IntegrationError
from app.integrations.processors.safeconsig.client import SafeConsigClient
from app.integrations.processors.safeconsig.config import SafeConsigConfig


def main() -> int:
    try:
        config = SafeConsigConfig.from_env("SAFECONSIG_HML")
    except IntegrationError as exc:
        print(f"[ERRO] Configuração inválida: {exc}", file=sys.stderr)
        return 1

    client = SafeConsigClient(config)
    try:
        client.autenticar()
    except IntegrationError as exc:
        print(f"[ERRO] Falha na autenticação: {exc}", file=sys.stderr)
        return 1

    print("✓ Autenticação SafeConsig HML bem-sucedida.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
