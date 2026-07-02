from app.utils.dates import derivar_competencia


def test_offset_zero_competencia_e_o_mes_do_corte():
    assert derivar_competencia("20/07/2026", 0) == "07/2026"


def test_offset_mais_um_fecha_o_proximo_mes():
    # corte de julho fecha agosto (caso validado: duque_de_caxias_rj, IPMDC)
    assert derivar_competencia("20/07/2026", 1) == "08/2026"


def test_offset_negativo():
    assert derivar_competencia("05/07/2026", -1) == "06/2026"


def test_virada_de_ano():
    assert derivar_competencia("20/12/2026", 1) == "01/2027"


def test_virada_de_ano_para_tras():
    assert derivar_competencia("01/2026", -1) == "12/2025"


def test_aceita_competencia_mm_yyyy():
    assert derivar_competencia("07/2026", 0) == "07/2026"
    assert derivar_competencia("07/2026", 1) == "08/2026"


def test_none_para_garbage():
    assert derivar_competencia(None) is None
    assert derivar_competencia("") is None
    assert derivar_competencia("ver tabela") is None
    assert derivar_competencia("00/13/2026") is None  # mês inválido
