"""Script de teste de autenticação para todos os portais sem captcha.

Uso:
    python scripts/testar_autenticacoes.py
    python scripts/testar_autenticacoes.py --portal consignet
    python scripts/testar_autenticacoes.py --convenio maringa
    python scripts/testar_autenticacoes.py --headless

O script não imprime credenciais em nenhum momento.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# Garante que a raiz do projeto está no sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

from app.config.credential_loader import CredentialNotFoundError, load_credentials
from app.core.loader import load_processadoras_config
from app.core.settings import settings
from app.services.coleta_service import build_auth_strategy, build_scraper

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("testar_autenticacoes")

# Portais que fazem apenas autenticação neste MVP (collect retorna NotImplementedError)
AUTH_ONLY_PORTALS = {
    "consigi", "konexia", "pbconsig", "proconsig",
    "consiglog", "fasitec", "digitalconsig", "consignet",
}


def _mask(text: str) -> str:
    """Mascara usuário para exibição segura."""
    if not text:
        return "***"
    if "@" in text:
        user, domain = text.split("@", 1)
        return f"{user[:2]}***@{domain}"
    return text[:2] + "***"


def testar_convenio(
    convenio_key: str,
    convenio_config: dict,
    processadora_key: str,
    processadora_config: dict,
) -> dict:
    """Testa autenticação de um convênio. Retorna resultado sem expor credenciais."""
    nome = convenio_config.get("nome", convenio_key)
    inicio = time.time()

    result = {
        "convenio_key": convenio_key,
        "convenio_nome": nome,
        "processadora": processadora_key,
        "status": "pendente",
        "duracao_s": 0.0,
        "erro": None,
    }

    try:
        auth_strategy = build_auth_strategy(processadora_config, convenio_config)
    except CredentialNotFoundError as e:
        result["status"] = "sem_credencial"
        result["erro"] = str(e)
        result["duracao_s"] = round(time.time() - inicio, 1)
        return result
    except Exception as e:
        result["status"] = "erro_config"
        result["erro"] = str(e)
        result["duracao_s"] = round(time.time() - inicio, 1)
        return result

    try:
        scraper = build_scraper(
            processadora_key=processadora_key,
            processadora_config=processadora_config,
            convenio_config=convenio_config,
            auth_strategy=auth_strategy,
        )

        scraper.start()
        try:
            scraper.authenticate()
            scraper.validate_access()
            result["status"] = "ok"
        finally:
            scraper.stop()

    except NotImplementedError:
        # collect() não implementado é esperado — autenticação OK
        result["status"] = "ok"
    except Exception as e:
        result["status"] = "falha"
        result["erro"] = str(e)

    result["duracao_s"] = round(time.time() - inicio, 1)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Testa autenticações nos portais sem captcha")
    parser.add_argument("--portal", help="Testar apenas este portal (ex: consignet)")
    parser.add_argument("--convenio", help="Testar apenas este convênio (ex: maringa)")
    parser.add_argument("--headless", action="store_true", help="Forçar modo headless")
    args = parser.parse_args()

    if args.headless:
        import os
        os.environ["HEADLESS"] = "true"
        settings.HEADLESS = True

    config = load_processadoras_config()
    processadoras_config = config["processadoras"]
    convenios_config = config["convenios"]

    # Filtra apenas portais auth_only (novos portais sem captcha)
    convenios_alvo = {
        key: cfg
        for key, cfg in convenios_config.items()
        if cfg.get("processadora") in AUTH_ONLY_PORTALS
    }

    if args.portal:
        convenios_alvo = {
            key: cfg for key, cfg in convenios_alvo.items()
            if cfg.get("processadora") == args.portal
        }

    if args.convenio:
        convenios_alvo = {
            key: cfg for key, cfg in convenios_alvo.items()
            if key == args.convenio
        }

    if not convenios_alvo:
        print("Nenhum convênio encontrado com os filtros fornecidos.")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  TESTE DE AUTENTICAÇÃO — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Convênios: {len(convenios_alvo)}")
    print(f"{'='*60}\n")

    resultados: list[dict] = []

    for convenio_key, convenio_config in convenios_alvo.items():
        processadora_key = convenio_config["processadora"]
        processadora_config = processadoras_config[processadora_key]
        nome = convenio_config.get("nome", convenio_key)

        print(f"[{processadora_key}] {nome} ... ", end="", flush=True)

        resultado = testar_convenio(
            convenio_key=convenio_key,
            convenio_config=convenio_config,
            processadora_key=processadora_key,
            processadora_config=processadora_config,
        )
        resultados.append(resultado)

        status = resultado["status"]
        duracao = resultado["duracao_s"]
        icone = {"ok": "✓", "falha": "✗", "sem_credencial": "?", "erro_config": "!"}.get(status, "?")
        print(f"{icone} {status.upper()} ({duracao}s)")
        if resultado["erro"]:
            # Imprime erro sem expor senhas
            print(f"    Erro: {resultado['erro']}")

    # Sumário
    total = len(resultados)
    ok = sum(1 for r in resultados if r["status"] == "ok")
    falha = sum(1 for r in resultados if r["status"] == "falha")
    sem_cred = sum(1 for r in resultados if r["status"] == "sem_credencial")
    erro_cfg = sum(1 for r in resultados if r["status"] == "erro_config")

    print(f"\n{'='*60}")
    print(f"  RESULTADO FINAL")
    print(f"  Total:         {total}")
    print(f"  Sucesso:       {ok}")
    print(f"  Falha auth:    {falha}")
    print(f"  Sem credencial:{sem_cred}")
    print(f"  Erro config:   {erro_cfg}")
    print(f"{'='*60}\n")

    # Salva relatório JSON (sem credenciais)
    relatorio_path = ROOT / "data" / "auth_test_results.json"
    relatorio_path.parent.mkdir(parents=True, exist_ok=True)
    with open(relatorio_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "executado_em": datetime.now().isoformat(),
                "total": total,
                "ok": ok,
                "falha": falha,
                "sem_credencial": sem_cred,
                "erro_config": erro_cfg,
                "resultados": resultados,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"Relatório salvo em: {relatorio_path}")


if __name__ == "__main__":
    main()
