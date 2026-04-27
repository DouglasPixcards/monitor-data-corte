from __future__ import annotations

from app.auth.certificate_auth import CertificateAuthStrategy
from app.auth.user_pass_auth import LoginPasswordAuthStrategy
from app.core.loader import load_processadoras_config
from app.scrapers.consigfacil.scraper import ConsigFacilScraper
from app.scrapers.safeconsig.scraper import SafeConsigScraper
from app.scrapers.consigup.scraper import ConsigUpScraper


def build_auth_strategy(processadora_config: dict, convenio_config: dict):
    auth_type = processadora_config["auth_type"]

    if auth_type == "route_certificate":
        return CertificateAuthStrategy()

    if auth_type == "login_password":
        return LoginPasswordAuthStrategy(
            username=convenio_config["credentials"]["username"],
            password=convenio_config["credentials"]["password"],
            selectors=processadora_config["selectors"],
        )

    raise ValueError(f"Tipo de autenticação não suportado: {auth_type}")


def build_scraper(
    processadora_key: str,
    processadora_config: dict,
    convenio_config: dict,
    auth_strategy,
):
    if processadora_key == "consigfacil":
        return ConsigFacilScraper(
            processadora_config=processadora_config,
            convenio_config=convenio_config,
            auth_strategy=auth_strategy,
        )

    if processadora_key == "safeconsig":
        return SafeConsigScraper(
            processadora_config=processadora_config,
            convenio_config=convenio_config,
            auth_strategy=auth_strategy,
        )
    
    if processadora_key == "consigup":
        return ConsigUpScraper(
            processadora_config=processadora_config,
            convenio_config=convenio_config,
            auth_strategy=auth_strategy,
        )

    raise ValueError(f"Scraper não suportado para processadora: {processadora_key}")


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

    return {
        "convenio_key": convenio_key,
        "processadora": processadora_key,
        "convenio": convenio_config.get("nome"),
        "status": resultado.get("status"),
        "dados": resultado.get("dados", []),
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
        return "erro"

    total = len(resultados_convenios)
    sucessos = sum(1 for item in resultados_convenios if item["status"] == "ok")

    if sucessos == total:
        return "ok"

    if sucessos == 0:
        return "erro"

    return "partial_success"


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
        auth_strategy = build_auth_strategy(processadora_config, convenio_config)

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
            continue

        for record in resultado_convenio["dados"]:
            records_consolidados.append({
                "convenio_key": convenio_key,
                "convenio_nome": convenio_config.get("nome"),
                "folha": record.get("folha"),
                "mes_atual": record.get("mes_atual"),
                "data_corte": record.get("data_corte"),
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