"""Scraper para o portal Konexia (konexia-it.com).

Tecnologia: JSF/PrimeFaces (.xhtml) — MESMA plataforma do ConSIGI (era um clone literal).
Reusa toda a coleta do ConSIGI; só a config (validacao/selectors) difere. Convênios: Planaltina.
"""
from __future__ import annotations

from app.scrapers.consigi.scraper import ConsigiScraper


class KonexiaScraper(ConsigiScraper):
    """Idêntico ao ConSIGI (mesma plataforma) — sem lógica própria."""
