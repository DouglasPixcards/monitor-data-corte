"""ConsigFácil: a data de corte vem SÓ do card "Datas de Fechamento", nunca do
card "Mensagens" (que traz timestamps de aviso). Perfil sem a seção → falha
tipada (sem_dado), jamais data falsa.

Roda o scraper real contra HTML local (sem portal/rede). Pula se o Chromium
não iniciar.
"""
from __future__ import annotations

import pytest

from app.core.exceptions import CollectionError
from app.scrapers.consigfacil.scraper import ConsigFacilScraper


# Estrutura fiel ao portal: card "Mensagens" (table-consig, com timestamps) +
# card "Datas de Fechamento" (table-consig-info, com a data real). Cabeçalho em
# <th>, dados em <td> — como no portal.
def _pagina(com_datas: bool, data_valor: str = "13/08/2026") -> str:
    card_datas = f"""
      <div class="card mb-3">
        <div class="card-header">Datas de Fechamento</div>
        <div class="card-body">
          <table class="table table-consig-info">
            <tbody>
              <tr><th>Folha</th><th>Mês atual</th><th>Data de fechamento</th></tr>
              <tr><td>Prefeitura Municipal de Itaituba</td><td>Agosto de 2026</td><td>{data_valor}</td></tr>
              <tr><td>Ver outros meses</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    """ if com_datas else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"></head><body>
      <div class="card mb-3">
        <div class="card-header">Mensagens</div>
        <div class="card-body">
          <table class="table table-consig">
            <thead><tr><th>Data</th><th>Assunto</th><th>Status</th></tr></thead>
            <tbody>
              <tr><td>15/07/2026 12:06</td><td>Fechamento/Corte: Agosto/2026</td><td></td></tr>
            </tbody>
          </table>
        </div>
      </div>
      {card_datas}
    </body></html>"""


def _scraper_com_pagina(html: str, tmp_path):
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # pragma: no cover
        pytest.skip(f"playwright indisponível: {e}")

    fixture = tmp_path / "consignatario.html"
    fixture.write_text(html, encoding="utf-8")

    sc = ConsigFacilScraper(
        processadora_config={}, convenio_config={"nome": "Itaituba"}, auth_strategy=object()
    )
    pw = sync_playwright().start()
    try:
        browser = pw.chromium.launch(headless=True)
    except Exception as e:  # pragma: no cover
        pw.stop()
        pytest.skip(f"Chromium não pôde iniciar: {e}")
    page = browser.new_context().new_page()
    page.set_default_timeout(5000)
    page.goto(fixture.as_uri())
    sc.page = page
    return sc, (browser, pw)


def test_le_datas_de_fechamento_ignora_mensagens(tmp_path):
    sc, (browser, pw) = _scraper_com_pagina(_pagina(com_datas=True), tmp_path)
    try:
        dados = sc.collect()
    finally:
        browser.close(); pw.stop()
    assert len(dados) == 1
    assert dados[0]["data_corte"] == "13/08/2026"       # do card certo
    assert dados[0]["folha"] == "Prefeitura Municipal de Itaituba"
    assert "15/07/2026" not in [d["data_corte"] for d in dados]  # NUNCA a mensagem


def test_secao_ausente_falha_tipada_sem_dado(tmp_path):
    # Perfil restrito: só o card Mensagens existe. Não pode inventar data.
    sc, (browser, pw) = _scraper_com_pagina(_pagina(com_datas=False), tmp_path)
    try:
        with pytest.raises(CollectionError) as exc:
            sc.collect()
    finally:
        browser.close(); pw.stop()
    assert exc.value.categoria == "sem_dado"


def test_data_com_horario_de_mensagem_e_rejeitada(tmp_path):
    # Mesmo dentro do card certo, um valor com horário (timestamp) não é corte.
    html = _pagina(com_datas=True, data_valor="15/07/2026 12:06")
    sc, (browser, pw) = _scraper_com_pagina(html, tmp_path)
    try:
        with pytest.raises(CollectionError) as exc:
            sc.collect()
    finally:
        browser.close(); pw.stop()
    assert exc.value.categoria == "sem_dado"
