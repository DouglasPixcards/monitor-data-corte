"""ConsigNet: escolhe o <h3> que é DATA (ignora os numéricos das métricas).

Regressão do bug: pegava o primeiro <h3> ('0') → o pipeline normalizava para '00/08/2026'.
"""
from app.scrapers.consignet.scraper import _escolher_data_corte
from app.utils.dates import normalizar_data_corte


def test_ignora_zero_e_pega_a_data():
    # exatamente o caso do bug: '0' antes de '10 Jul'
    assert _escolher_data_corte(["0", "10 Jul"]) == "10 Jul"


def test_ignora_todas_as_metricas():
    assert _escolher_data_corte(["34", "0", "0", "10 Jul"]) == "10 Jul"


def test_aceita_data_com_barra():
    assert _escolher_data_corte(["0", "10/07/2026"]) == "10/07/2026"


def test_so_numeros_retorna_none():
    # métrica sem data → None (melhor que devolver lixo)
    assert _escolher_data_corte(["0", "34"]) is None


def test_rejeita_palavra_que_nao_e_mes():
    # "2 New" tem número+palavra, mas 'new' não é mês → não é a data de corte
    assert _escolher_data_corte(["2 New", "10 Jul"]) == "10 Jul"


def test_aceita_mes_em_portugues():
    # se o portal vier em pt, "10 Ago" também é data válida
    assert _escolher_data_corte(["0", "10 Ago"]) == "10 Ago"
    assert normalizar_data_corte("10 Ago", coletado_em="2026-01-01T10:00:00") == "10/08/2026"


def test_vazio_e_none():
    assert _escolher_data_corte([]) is None
    assert _escolher_data_corte(None) is None


def test_espacos_extras():
    assert _escolher_data_corte(["  ", "  10 Jul  "]) == "10 Jul"


def test_cadeia_completa_ate_normalizar():
    # o valor escolhido tem que virar 10/07/2026 no pipeline (não 00/08/2026)
    valor = _escolher_data_corte(["0", "10 Jul"])
    assert normalizar_data_corte(valor, coletado_em="2026-06-29T10:00:00") == "10/07/2026"
