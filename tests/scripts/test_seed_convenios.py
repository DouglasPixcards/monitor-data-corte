"""Helpers puros do seed: normalização de nome, auto-match e heurística de automático."""
from scripts.seed_convenios_registro import melhor_match, normalizar_nome, parece_automatico

MONITOR = {
    "contagem": "Contagem", "maringa": "Maringá", "guarulhos": "Guarulhos",
    "duque_de_caxias_rj": "Duque de Caxias-RJ", "planaltina": "Planaltina",
    "paraiba": "Paraíba",
}


def test_normalizar_remove_acentos_prefixos_e_pontuacao():
    assert normalizar_nome("PREF DE CONTAGEM - MG") == "contagem mg"
    assert normalizar_nome("GOVERNO DA PARAIBA - PB") == "paraiba pb"
    assert normalizar_nome("Maringá") == "maringa"


def test_match_propoe_com_score_alto():
    key, score = melhor_match("PREF DE CONTAGEM - MG", MONITOR)
    assert key == "contagem" and score >= 0.85


def test_match_paraiba():
    key, score = melhor_match("GOVERNO DA PARAIBA - PB", MONITOR)
    assert key == "paraiba" and score >= 0.6


def test_match_duque():
    key, _ = melhor_match("PREF DE DUQUE DE CAXIAS - RJ", MONITOR)
    assert key == "duque_de_caxias_rj"


def test_sem_match_score_baixo():
    _, score = melhor_match("COMLURB", MONITOR)
    assert score < 0.6


def test_parece_automatico():
    assert parece_automatico("DESC AUTOMATICO - PROD BENEF") is True
    assert parece_automatico("Desconto automatico") is True
    assert parece_automatico("SEM REMESSA (autarquia RJ)") is True
    assert parece_automatico("ENVIAR CREDITO E BENEFICIO - 14:00") is False
    assert parece_automatico(None) is False
