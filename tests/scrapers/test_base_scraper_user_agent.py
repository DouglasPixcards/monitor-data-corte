"""_user_agent_headless: headless anuncia "HeadlessChrome" no UA e WAFs
(ex.: Consignet) respondem 403 — em headless o UA vira Chrome comum com a
versão real do engine; headful mantém o UA nativo."""
from unittest.mock import MagicMock

from app.scrapers.base_scraper import BaseScraper


class _Fake(BaseScraper):
    def __init__(self):
        super().__init__({}, {"processadora": "x"}, object())

    def authenticate(self):
        pass

    def validate_access(self):
        pass

    def collect(self):
        return []


def _scraper(headless: bool) -> _Fake:
    s = _Fake()
    s.headless = headless
    return s


def test_headful_mantem_ua_nativo():
    s = _scraper(headless=False)
    s.browser = MagicMock(version="140.0.7339.16")
    assert s._user_agent_headless() is None


def test_headless_usa_chrome_comum_com_versao_real_do_engine():
    s = _scraper(headless=True)
    s.browser = MagicMock(version="140.0.7339.16")
    ua = s._user_agent_headless()
    assert "Headless" not in ua
    assert "Chrome/140.0.7339.16" in ua
    assert ua.startswith("Mozilla/5.0")


def test_headless_sem_browser_retorna_none():
    # Caminho do launch_persistent_context (user_data_dir): browser fica None.
    s = _scraper(headless=True)
    assert s._user_agent_headless() is None
