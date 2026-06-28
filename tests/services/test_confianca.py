from app.services.confianca import classificar_confianca, mudou_dia_corte


def test_estavel_sem_mudancas():
    assert classificar_confianca(0) == "estavel"


def test_media_poucas_mudancas():
    assert classificar_confianca(1) == "media"
    assert classificar_confianca(2) == "media"


def test_instavel_muitas_mudancas():
    assert classificar_confianca(3) == "instavel"
    assert classificar_confianca(10) == "instavel"


def test_mudou_dia_corte_dia_diferente():
    assert mudou_dia_corte("10/05/2026", "13/05/2026") is True


def test_avanco_de_mes_mesmo_dia_nao_conta():
    # progressão normal (dia 10 estável, mês rola) NÃO é instabilidade
    assert mudou_dia_corte("10/05/2026", "10/06/2026") is False


def test_competencia_e_none_nao_contam():
    assert mudou_dia_corte("06/2026", "07/2026") is False
    assert mudou_dia_corte(None, "10/05/2026") is False
