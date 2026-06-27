"""base_scraper.run() propaga a categoria tipada de CollectionError."""
from app.core.exceptions import CollectionError
from app.scrapers.base_scraper import BaseScraper


class _Fake(BaseScraper):
    def __init__(self, exc):
        super().__init__({}, {"processadora": "x"}, object())
        self._exc = exc

    def start(self):
        pass

    def stop(self):
        pass

    def authenticate(self):
        if self._exc:
            raise self._exc

    def validate_access(self):
        pass

    def collect(self):
        return []


def test_collection_error_propaga_categoria():
    r = _Fake(CollectionError("auth ruim", categoria="auth_falhou")).run()
    assert r["status"] == "erro"
    assert r["erro_categoria"] == "auth_falhou"


def test_runtime_error_sem_categoria():
    r = _Fake(RuntimeError("xpto")).run()
    assert r["status"] == "erro"
    assert r["erro_categoria"] is None


def test_sucesso_erro_categoria_none():
    r = _Fake(None).run()
    assert r["status"] == "ok"
    assert r["erro_categoria"] is None
