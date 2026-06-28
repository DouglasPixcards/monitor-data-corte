from app.utils.dates import salto_data_corte_suspeito, validar_data_corte

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


def test_salto_pequeno_nao_e_suspeito():
    assert salto_data_corte_suspeito("10/05/2026", "08/05/2026") is False  # 2 dias


def test_salto_grande_e_suspeito():
    assert salto_data_corte_suspeito("10/05/2026", "28/06/2026") is True   # 49 dias


def test_salto_so_avalia_ddmmyyyy():
    assert salto_data_corte_suspeito("06/2026", "08/2026") is False        # MM/YYYY
    assert salto_data_corte_suspeito(None, "10/05/2026") is False
    assert salto_data_corte_suspeito("ver tabela", "10/05/2026") is False


def test_salto_no_limite_trava_o_teto():
    # Exatamente _MAX_SALTO_DIAS (45) NÃO é suspeito; 46 é — trava o teto de 45.
    assert salto_data_corte_suspeito("10/05/2026", "24/06/2026") is False  # 45 dias
    assert salto_data_corte_suspeito("10/05/2026", "25/06/2026") is True   # 46 dias
