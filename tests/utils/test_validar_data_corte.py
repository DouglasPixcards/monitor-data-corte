from app.utils.dates import validar_data_corte

CE = "2026-04-29T08:00:00"  # coletado_em → ano_ref = 2026


def test_dd_mm_yyyy_valida():
    assert validar_data_corte("10/05/2026", CE) is True


def test_data_impossivel_invalida():
    assert validar_data_corte("31/02/2026", CE) is False


def test_competencia_mm_yyyy_valida():
    # Estimativa SafeConsig (competência) é válida.
    assert validar_data_corte("06/2026", CE) is True


def test_garbage_invalido():
    assert validar_data_corte("ver tabela", CE) is False


def test_none_e_vazio_invalidos():
    assert validar_data_corte(None, CE) is False
    assert validar_data_corte("", CE) is False


def test_ano_fora_da_janela_invalido():
    assert validar_data_corte("10/05/2099", CE) is False
    assert validar_data_corte("10/05/2020", CE) is False


def test_ano_na_borda_valido():
    assert validar_data_corte("10/05/2025", CE) is True   # ano_ref - 1
    assert validar_data_corte("10/05/2027", CE) is True   # ano_ref + 1


def test_sem_coletado_em_dispensa_janela_mas_mantem_calendario():
    # Sem coletado_em: não checa a janela de ano (sem datetime.now()), mas ainda
    # rejeita data de calendário impossível.
    assert validar_data_corte("10/05/2099", None) is True
    assert validar_data_corte("31/02/2099", None) is False
