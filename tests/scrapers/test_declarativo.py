import pytest

from app.core.exceptions import CollectionError
from app.scrapers.consigi.scraper import ConsigiScraper
from app.scrapers.consigup.scraper import ConsigUpScraper
from app.scrapers.declarativo import (
    com_retry,
    linhas_de_tabela,
    primeiro_grupo_regex,
    texto_apos_separador,
    validar_acesso,
    valor_opcional_apos_separador,
)
from app.scrapers.consigfacil.scraper import ConsigFacilScraper
from app.scrapers.konexia.scraper import KonexiaScraper
from app.scrapers.proconsig.scraper import ProconsigScraper


# ── Fakes de Playwright ───────────────────────────────────────────────────────
class _Loc:
    def __init__(self, count=1, text=""):
        self._count = count
        self._text = text
        self._filhos = {}   # sel -> _Loc (tr/td aninhados)
        self._itens = []    # para nth

    def count(self):
        return self._count

    def inner_text(self):
        return self._text

    def wait_for(self, **kwargs):
        self.wait_kwargs = kwargs

    def locator(self, sel):
        return self._filhos.get(sel, _Loc(count=0))

    def nth(self, i):
        return self._itens[i]

    @property
    def first(self):
        return self


def _tabela(linhas, linhas_seletor="tr"):
    tr = _Loc(count=len(linhas))
    for cells in linhas:
        td = _Loc(count=len(cells))
        td._itens = [_Loc(text=c) for c in cells]
        row = _Loc()
        row._filhos = {"td": td}
        tr._itens.append(row)
    tabela = _Loc()
    tabela._filhos = {linhas_seletor: tr}
    return tabela


class _Page:
    def __init__(self, url="", locators=None, body=""):
        self.url = url
        self._locators = locators or {}
        self._body = body
        self.aguardou = None

    def locator(self, sel):
        if sel == "body":
            return _Loc(count=1, text=self._body)
        return self._locators.get(sel, _Loc(count=0))

    def wait_for_url(self, pattern, timeout=None):
        self.aguardou = pattern

    def wait_for_timeout(self, ms):
        pass


# ── validar_acesso ────────────────────────────────────────────────────────────
def test_validar_falha_seletor():
    page = _Page(url="https://x", locators={"#erro": _Loc(count=1)})
    with pytest.raises(CollectionError) as ei:
        validar_acesso(page, {"falha_seletores": ["#erro"]}, 1000)
    assert ei.value.categoria == "auth_falhou"


def test_validar_falha_keyword_expirada_vira_credencial_expirada():
    page = _Page(url="https://x", body="Sua senha expirada, renove")
    with pytest.raises(CollectionError) as ei:
        validar_acesso(page, {"falha_keywords": ["xpirad", "inválid"]}, 1000)
    assert ei.value.categoria == "credencial_expirada"


def test_validar_falha_url_login():
    page = _Page(url="https://portal/login.xhtml")
    with pytest.raises(CollectionError) as ei:
        validar_acesso(page, {"falha_url": ["login.xhtml"]}, 1000)
    assert ei.value.categoria == "auth_falhou"


def test_validar_sucesso_por_seletor_nao_levanta():
    page = _Page(url="https://portal/home", locators={"text=Sair": _Loc(count=1)})
    validar_acesso(page, {"falha_url": ["login.xhtml"], "sucesso_seletores": ["text=Sair"]}, 1000)


def test_validar_sucesso_por_url():
    page = _Page(url="https://portal/Inicio/Inicio.aspx")
    validar_acesso(page, {"sucesso_url": ["Inicio.aspx"]}, 1000)


def test_validar_aguardar_url_chama_wait():
    page = _Page(url="https://portal/Inicio/Inicio.aspx")
    validar_acesso(page, {"aguardar_url": "**/Inicio/Inicio.aspx"}, 1000)
    assert page.aguardou == "**/Inicio/Inicio.aspx"


def test_validar_sem_regras_noop():
    validar_acesso(_Page(url="x"), {}, 1000)


# ── helpers de extração ───────────────────────────────────────────────────────
def test_texto_apos_separador():
    page = _Page(locators={"li": _Loc(text="Dia de corte: 10/05/2026")})
    assert texto_apos_separador(page, "li") == "10/05/2026"


def test_valor_opcional_ausente_none():
    assert valor_opcional_apos_separador(_Page(), "li") is None


def test_valor_opcional_presente():
    page = _Page(locators={"li": _Loc(count=1, text="Margem: 06/2026")})
    assert valor_opcional_apos_separador(page, "li") == "06/2026"


def test_linhas_de_tabela():
    page = _Page(locators={"#t": _tabela([["h1", "h2"], ["10/05", "CORTE DIA 10"]])})
    assert linhas_de_tabela(page, "#t") == [["h1", "h2"], ["10/05", "CORTE DIA 10"]]


def test_primeiro_grupo_regex():
    assert primeiro_grupo_regex("CORTE DIA 10 do mês", r"CORTE\s+DIA\s+(\d{1,2})") == "10"
    assert primeiro_grupo_regex("sem match", r"(\d+)") is None


# ── scrapers migrados (smoke) ─────────────────────────────────────────────────
def test_konexia_reusa_consigi():
    # dedup: Konexia É um ConsigiScraper (mesma plataforma)
    assert issubclass(KonexiaScraper, ConsigiScraper)


def test_consigi_collect_usa_helpers():
    page = _Page(locators={
        'li:has-text("Dia de corte:")': _Loc(count=1, text="Dia de corte: 10/05/2026"),
        'li:has-text("Última atualização de margem:")': _Loc(count=1, text="Margem: 06/2026"),
    })
    sc = ConsigiScraper({}, {"processadora": "consigi"}, object())
    sc.page = page
    assert sc.collect() == [{"data_corte": "10/05/2026", "folha": None, "mes_atual": "06/2026"}]


def test_consigup_collect_tabela_regex():
    page = _Page(locators={"#MainContent_gvAvisos": _tabela([
        ["Data", "Descrição"],
        ["01/06/2026", "AVISO CORTE DIA 7 referente"],
    ])})
    sc = ConsigUpScraper({}, {"processadora": "consigup"}, object())
    sc.page = page
    assert sc.collect() == [
        {"folha": "AVISO CORTE DIA 7 referente", "mes_atual": "01/06/2026", "data_corte": "07"}
    ]


# ── resiliência (timeout + retry — regressões pegas na revisão) ────────────────
def test_linhas_de_tabela_passa_timeout():
    t = _tabela([["a"]])
    page = _Page(locators={"#t": t})
    linhas_de_tabela(page, "#t", timeout=99999)
    assert t.wait_kwargs.get("timeout") == 99999


def test_consigup_usa_timeout_grande_da_config():
    from app.core.settings import settings
    t = _tabela([["Data", "Desc"], ["01/06", "CORTE DIA 5"]])
    page = _Page(locators={"#MainContent_gvAvisos": t})
    sc = ConsigUpScraper({}, {"processadora": "consigup"}, object())
    sc.page = page
    sc.collect()
    assert t.wait_kwargs.get("timeout") == settings.TIMEOUT_MS


def test_com_retry_sucede_apos_falha_transiente():
    chamadas = []

    def fn():
        chamadas.append(1)
        if len(chamadas) < 2:
            raise RuntimeError("flaky")
        return "ok"

    assert com_retry(_Page(), fn, tentativas=3, espera_ms=0) == "ok"
    assert len(chamadas) == 2


def test_com_retry_relevanta_apos_esgotar():
    def fn():
        raise RuntimeError("sempre falha")

    with pytest.raises(RuntimeError):
        com_retry(_Page(), fn, tentativas=2, espera_ms=0)


def test_linhas_de_tabela_com_seletor_de_linha():
    page = _Page(locators={"#t": _tabela([["a", "b"]], linhas_seletor="tbody tr")})
    assert linhas_de_tabela(page, "#t", linhas_seletor="tbody tr") == [["a", "b"]]


# ── ProConsig + ConsigFácil migrados ──────────────────────────────────────────
def test_proconsig_collect_usa_helpers():
    page = _Page(locators={
        'p:has-text("Fim:")': _Loc(count=1, text="Janela — Fim: 10/05/2026"),
        'p:has-text("Referência:")': _Loc(count=1, text="Referência: 05/2026"),
    })
    sc = ProconsigScraper({}, {"processadora": "proconsig"}, object())
    sc.page = page
    assert sc.collect() == [{"data_corte": "10/05/2026", "folha": None, "mes_atual": "05/2026"}]


def test_consigfacil_collect_tabela_pula_vazia():
    page = _Page(
        url="https://x/pagina_consignatario.php",  # consignatario → sem navegação
        locators={"table.table.table-consig-info": _tabela([
            ["Folha A", "05/2026", "10/05/2026"],
            ["", "", ""],  # linha vazia → pulada
        ], linhas_seletor="tbody tr")},
    )
    sc = ConsigFacilScraper({}, {"processadora": "consigfacil"}, object())
    sc.page = page
    assert sc.collect() == [{"folha": "Folha A", "mes_atual": "05/2026", "data_corte": "10/05/2026"}]


def test_consigfacil_validate_fail_closed():
    sc = ConsigFacilScraper({}, {"processadora": "consigfacil"}, object())
    sc.page = _Page(url="https://x/login.php")
    with pytest.raises(RuntimeError):
        sc.validate_access()


def test_consigfacil_validate_ok_consignatario():
    sc = ConsigFacilScraper({}, {"processadora": "consigfacil"}, object())
    sc.page = _Page(url="https://x/pagina_consignatario.php")
    sc.validate_access()  # não levanta
