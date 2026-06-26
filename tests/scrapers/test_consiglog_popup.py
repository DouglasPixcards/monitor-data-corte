"""Handler do popup "Usuário já logado" da ConsigLog: esperar o modal AJAX
renderizar antes de decidir que não há popup.

Bug: ``is_visible(timeout=3000)`` NÃO espera — checa na hora. Se o modal AJAX
renderiza alguns ms após o login, o handler vê "nada" e segue, deixando o popup
aberto (bloqueia o gvOrgao). Fix: ``wait_for(state="visible", timeout=...)``,
que espera o elemento aparecer.

Page falsa (mock): o botão de confirmação NÃO está visível no instante imediato
(``is_visible``→False), mas aparece quando se espera (``wait_for`` sucede) —
exatamente o cenário do modal que renderiza tarde.
"""
from unittest.mock import MagicMock

from app.scrapers.consiglog.scraper import ConsiglogScraper

POPUP_SELECTOR = "#ucAjaxModalPopupConfirmacao1_btnConfirmarPopup"


class _FakeConfirmBtn:
    def __init__(self, *, visivel_na_hora: bool, visivel_apos_espera: bool) -> None:
        self._imediato = visivel_na_hora
        self._apos_espera = visivel_apos_espera
        self.clicked = False

    def is_visible(self, timeout=None) -> bool:
        # Imediato, sem esperar — modelo do bug.
        return self._imediato

    def wait_for(self, state=None, timeout=None) -> None:
        # Espera de verdade: se o modal renderiza dentro do prazo, sucede.
        if not self._apos_espera:
            raise TimeoutError("popup não apareceu no prazo")

    def click(self, **kwargs) -> None:
        self.clicked = True


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakePage:
    def __init__(self, btn: _FakeConfirmBtn) -> None:
        self._btn = btn
        self.url = "https://saec.consiglog.com.br/LoginSegundaEtapa.aspx"

    def locator(self, selector: str) -> _FakeConfirmBtn:
        return self._btn

    def expect_navigation(self, **kwargs) -> _Ctx:
        return _Ctx()

    def wait_for_load_state(self, *args, **kwargs) -> None:
        pass


def _scraper(btn: _FakeConfirmBtn) -> ConsiglogScraper:
    s = ConsiglogScraper(
        processadora_config={},
        convenio_config={"processadora": "consiglog", "base_url": "http://x"},
        auth_strategy=MagicMock(),  # super().authenticate() vira no-op
    )
    s.page = _FakePage(btn)
    return s


def test_popup_que_renderiza_tarde_e_confirmado():
    # Modal não visível na hora, mas aparece com espera → handler deve confirmar.
    btn = _FakeConfirmBtn(visivel_na_hora=False, visivel_apos_espera=True)
    _scraper(btn).authenticate()
    assert btn.clicked is True


def test_sem_popup_nao_clica_e_nao_levanta():
    btn = _FakeConfirmBtn(visivel_na_hora=False, visivel_apos_espera=False)
    _scraper(btn).authenticate()  # não deve levantar
    assert btn.clicked is False
