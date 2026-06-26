"""validate_access da ConsigLog: valida por CONTEÚDO, não pela URL.

O portal é ASP.NET WebForms — após o login a URL continua
``LoginSegundaEtapa.aspx`` (postback), exibindo a seleção de convênio
(``table#gvOrgao``). Validar pela URL dava falso-negativo. Agora:
- sucesso = presença de indicador de conteúdo (gvOrgao / dashboard), mesmo na
  URL de login;
- falha = campos de login na tela + mensagem de erro REAL (senha expirada /
  inválida / etc.). Os campos de login persistem mesmo logado, então a
  mensagem é o que distingue falha real do falso-negativo.

Page falsa (mock) — não toca portal. Mock é o tipo certo aqui porque o ponto do
fix é justamente a URL: precisamos controlar page.url, o que um HTML local
(file://) não permite.
"""
from unittest.mock import MagicMock

import pytest

from app.scrapers.consiglog.scraper import ConsiglogScraper

LOGIN2_URL = "https://saec.consiglog.com.br/LoginSegundaEtapa.aspx"
DASH_URL = "https://saec.consiglog.com.br/Default.aspx"


class _FakeLoc:
    def __init__(self, count: int, text: str = "") -> None:
        self._count = count
        self._text = text

    def count(self) -> int:
        return self._count

    @property
    def first(self):
        return self

    def inner_text(self) -> str:
        return self._text


class _FakePage:
    """page.url + page.locator(sel).count()/.first.inner_text() controlados."""

    def __init__(self, url: str, selectors: dict[str, tuple[int, str]]) -> None:
        self.url = url
        self._sel = selectors

    def locator(self, selector: str) -> _FakeLoc:
        count, text = self._sel.get(selector, (0, ""))
        return _FakeLoc(count, text)


def _scraper() -> ConsiglogScraper:
    s = ConsiglogScraper(
        processadora_config={},
        convenio_config={"processadora": "consiglog"},
        auth_strategy=MagicMock(),
    )
    return s


def test_pos_login_gvorgao_passa_mesmo_em_loginsegundaetapa():
    # O falso-negativo: logado (gvOrgao presente) mas URL ainda é login.
    s = _scraper()
    s.page = _FakePage(LOGIN2_URL, {"table#gvOrgao": (1, "Selecione o Convênio")})
    s.validate_access()  # não deve levantar


def test_senha_expirada_falha_com_mensagem():
    s = _scraper()
    s.page = _FakePage(LOGIN2_URL, {
        "#txtLogin": (1, "DCELESTINO"),
        "#txtSenha": (1, ""),
        "body": (1, "Senha do usuário está expirada."),
    })
    with pytest.raises(RuntimeError) as ei:
        s.validate_access()
    assert "expirada" in str(ei.value).lower()


def test_login_invalido_falha():
    s = _scraper()
    s.page = _FakePage(LOGIN2_URL, {
        "#txtLogin": (1, ""),
        "#txtSenha": (1, ""),
        "body": (1, "Usuário ou senha inválidos"),
    })
    with pytest.raises(RuntimeError):
        s.validate_access()


def test_dashboard_sair_passa():
    s = _scraper()
    s.page = _FakePage(DASH_URL, {"text=Sair": (1, "Sair")})
    s.validate_access()  # não deve levantar


def test_campos_login_sem_mensagem_de_erro_nao_derruba():
    # Spec: só falha se campos de login + mensagem de erro real. Sem mensagem
    # de erro e sem indicador de sucesso, não derruba pela URL (collect decide).
    s = _scraper()
    s.page = _FakePage(LOGIN2_URL, {
        "#txtLogin": (1, ""),
        "#txtSenha": (1, ""),
        "body": (1, "Login: Senha: Mostrar Senha"),
    })
    s.validate_access()  # não deve levantar
