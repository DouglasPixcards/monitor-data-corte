"""Registro central de portais: mapeia portal_key -> scraper class.

Adicionar um novo portal = importar o scraper + inserir na _REGISTRY.
O coleta_service usa este registro para instanciar scrapers dinamicamente.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.scrapers.base_scraper import BaseScraper

# Importações lazy para não quebrar a coleta se um scraper específico falhar no import
def _get_registry() -> dict[str, type]:
    from app.scrapers.consigfacil.scraper import ConsigFacilScraper
    from app.scrapers.consigup.scraper import ConsigUpScraper
    from app.scrapers.safeconsig.scraper import SafeConsigScraper
    from app.scrapers.consigi.scraper import ConsigiScraper
    from app.scrapers.konexia.scraper import KonexiaScraper
    from app.scrapers.pbconsig.scraper import PbconsigScraper
    from app.scrapers.proconsig.scraper import ProconsigScraper
    from app.scrapers.consiglog.scraper import ConsiglogScraper
    from app.scrapers.fasitec.scraper import FasitecScraper
    from app.scrapers.digitalconsig.scraper import DigitalconsigScraper
    from app.scrapers.consignet.scraper import ConsignetScraper

    return {
        "consigfacil": ConsigFacilScraper,
        "consigup": ConsigUpScraper,
        "safeconsig": SafeConsigScraper,
        "consigi": ConsigiScraper,
        "konexia": KonexiaScraper,
        "pbconsig": PbconsigScraper,
        "proconsig": ProconsigScraper,
        "consiglog": ConsiglogScraper,
        "fasitec": FasitecScraper,
        "digitalconsig": DigitalconsigScraper,
        "consignet": ConsignetScraper,
    }


def get_scraper_class(portal_key: str) -> type:
    registry = _get_registry()
    if portal_key not in registry:
        raise ValueError(f"Portal não registrado: {portal_key!r}. Registros: {list(registry)}")
    return registry[portal_key]
