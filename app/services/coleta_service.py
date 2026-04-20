from app.auth.certificate_auth import CertificateAuthStrategy
# from app.auth.login_password_auth import LoginPasswordAuthStrategy
from app.core.loader import load_processadoras_config
from app.scrapers.consigfacil.scraper import ConsigFacilScraper
from app.scrapers.safeconsig.scraper import SafeConsigScraper


def build_auth_strategy(processadora_config: dict):
    auth_type = processadora_config["auth_type"]

    if auth_type == "route_certificate":
        return CertificateAuthStrategy()

    if auth_type == "login_password":
        raise NotImplementedError("Estratégia de autenticação por login e senha ainda não implementada.")
        return LoginPasswordAuthStrategy(username="", password="")

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

    raise ValueError(f"Scraper não suportado para processadora: {processadora_key}")


def executar_coleta(convenio_key: str) -> dict:
    config = load_processadoras_config()

    convenio_config = config["convenios"][convenio_key]
    processadora_key = convenio_config["processadora"]
    processadora_config = config["processadoras"][processadora_key]

    auth_strategy = build_auth_strategy(processadora_config)
    scraper = build_scraper(
        processadora_key=processadora_key,
        processadora_config=processadora_config,
        convenio_config=convenio_config,
        auth_strategy=auth_strategy,
    )

    return scraper.run()