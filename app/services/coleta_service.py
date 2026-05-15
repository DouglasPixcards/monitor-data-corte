from __future__ import annotations

import logging

from app.auth.blur_reveal_auth import BlurRevealAuthStrategy
from app.auth.certificate_auth import CertificateAuthStrategy
from app.auth.two_step_auth import TwoStepAuthStrategy
from app.auth.user_pass_auth import LoginPasswordAuthStrategy
from app.config.credential_loader import CredentialNotFoundError, load_credentials
from app.config.portal_registry import get_scraper_class
from app.core.enums import AuthType, CollectionStatus
from app.core.loader import load_processadoras_config
from app.services.storage_helpers import now_iso
from app.utils.dates import normalizar_data_corte

logger = logging.getLogger(__name__)


def build_auth_strategy(processadora_config: dict, convenio_config: dict):
    auth_type = processadora_config["auth_type"]

    if auth_type == AuthType.CERTIFICATE:
        return CertificateAuthStrategy()

    if auth_type in (AuthType.LOGIN_PASSWORD, AuthType.TWO_STEP, AuthType.BLUR_REVEAL):
        # Suporta duas formas de credenciais:
        # 1. Legada: credentials.username / credentials.password direto no JSON (consigup/muana)
        # 2. Nova: credential_env_key -> lê do .env via credential_loader
        credentials = convenio_config.get("credentials")
        if credentials:
            username = credentials["username"]
            password = credentials["password"]
        else:
            env_key = convenio_config.get("credential_env_key")
            if not env_key:
                raise ValueError(
                    f"Convênio {convenio_config.get('nome')!r} não tem 'credentials' nem 'credential_env_key'."
                )
            portal, convenio_key = env_key.split("_", 1)
            username, password = load_credentials(portal, convenio_key)

        selectors = processadora_config["selectors"]
        if auth_type == AuthType.TWO_STEP:
            return TwoStepAuthStrategy(username=username, password=password, selectors=selectors)
        if auth_type == AuthType.BLUR_REVEAL:
            return BlurRevealAuthStrategy(username=username, password=password, selectors=selectors)
        return LoginPasswordAuthStrategy(username=username, password=password, selectors=selectors)

    raise ValueError(f"Tipo de autenticação não suportado: {auth_type}")


def build_scraper(
    processadora_key: str,
    processadora_config: dict,
    convenio_config: dict,
    auth_strategy,
):
    scraper_class = get_scraper_class(processadora_key)
    return scraper_class(
        processadora_config=processadora_config,
        convenio_config=convenio_config,
        auth_strategy=auth_strategy,
    )


def executar_coleta(convenio_key: str) -> dict:
    config = load_processadoras_config()

    convenio_config = config["convenios"][convenio_key]
    processadora_key = convenio_config["processadora"]
    processadora_config = config["processadoras"][processadora_key]

    auth_strategy = build_auth_strategy(processadora_config, convenio_config)
    scraper = build_scraper(
        processadora_key=processadora_key,
        processadora_config=processadora_config,
        convenio_config=convenio_config,
        auth_strategy=auth_strategy,
    )

    resultado = scraper.run()

    coletado_em = now_iso()
    dados_normalizados = [
        {
            **d,
            "data_corte": normalizar_data_corte(
                d.get("data_corte"), d.get("mes_atual"), coletado_em
            ),
        }
        for d in resultado.get("dados", [])
    ]

    return {
        "convenio_key": convenio_key,
        "processadora": processadora_key,
        "convenio": convenio_config.get("nome"),
        "status": resultado.get("status"),
        "dados": dados_normalizados,
        "erro": resultado.get("erro"),
    }


def _filtrar_convenios_da_processadora(
    processadora_key: str,
    convenios_config: dict,
) -> dict:
    return {
        convenio_key: convenio_config
        for convenio_key, convenio_config in convenios_config.items()
        if convenio_config["processadora"] == processadora_key
    }


def _calcular_status_lote(resultados_convenios: list[dict]) -> str:
    if not resultados_convenios:
        return CollectionStatus.ERROR

    total = len(resultados_convenios)
    sucessos = sum(1 for item in resultados_convenios if item["status"] == CollectionStatus.OK)

    if sucessos == total:
        return CollectionStatus.OK

    if sucessos == 0:
        return CollectionStatus.ERROR

    return CollectionStatus.PARTIAL_SUCCESS


def executar_coleta_lote(processadora_key: str) -> dict:
    config = load_processadoras_config()

    processadoras_config = config["processadoras"]
    convenios_config = config["convenios"]

    if processadora_key not in processadoras_config:
        raise ValueError(f"Processadora não encontrada: {processadora_key}")

    processadora_config = processadoras_config[processadora_key]
    convenios_da_processadora = _filtrar_convenios_da_processadora(
        processadora_key=processadora_key,
        convenios_config=convenios_config,
    )

    resultados_convenios: list[dict] = []
    records_consolidados: list[dict] = []

    for convenio_key, convenio_config in convenios_da_processadora.items():
        try:
            auth_strategy = build_auth_strategy(processadora_config, convenio_config)
        except CredentialNotFoundError as e:
            logger.error("Credenciais ausentes para %s: %s", convenio_key, e)
            resultados_convenios.append({
                "convenio_key": convenio_key,
                "convenio_nome": convenio_config.get("nome"),
                "status": "erro",
                "records_count": 0,
                "erro": str(e),
                "dados": [],
            })
            continue

        scraper = build_scraper(
            processadora_key=processadora_key,
            processadora_config=processadora_config,
            convenio_config=convenio_config,
            auth_strategy=auth_strategy,
        )

        resultado = scraper.run()

        resultado_convenio = {
            "convenio_key": convenio_key,
            "convenio_nome": convenio_config.get("nome"),
            "status": resultado.get("status"),
            "records_count": len(resultado.get("dados", [])),
            "erro": resultado.get("erro"),
            "dados": resultado.get("dados", []),
        }

        resultados_convenios.append(resultado_convenio)

        if resultado_convenio["status"] != "ok":
            logger.error(
                "Coleta falhou para %s (%s): %s",
                convenio_key,
                convenio_config.get("nome", ""),
                resultado_convenio.get("erro"),
            )
            continue

        coletado_em = now_iso()
        for record in resultado_convenio["dados"]:
            records_consolidados.append({
                "convenio_key": convenio_key,
                "convenio_nome": convenio_config.get("nome"),
                "folha": record.get("folha"),
                "mes_atual": record.get("mes_atual"),
                "data_corte": normalizar_data_corte(
                    record.get("data_corte"), record.get("mes_atual"), coletado_em
                ),
            })

    status_lote = _calcular_status_lote(resultados_convenios)

    return {
        "processadora": processadora_key,
        "status": status_lote,
        "total_convenios": len(resultados_convenios),
        "success_count": sum(1 for item in resultados_convenios if item["status"] == "ok"),
        "error_count": sum(1 for item in resultados_convenios if item["status"] != "ok"),
        "records": records_consolidados,
        "convenios": resultados_convenios,
    }
