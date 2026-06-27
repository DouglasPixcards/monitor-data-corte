from datetime import datetime
import app.services.janela_coleta as jc


def _dt(h, m):  # naive = hora-de-parede local; basta para a lógica de janela
    return datetime(2026, 6, 26, h, m)  # 2026-06-26 é sexta-feira


def test_meio_da_tarde_dentro():
    assert jc.dentro_da_janela_consigup(_dt(14, 0)) is True

def test_antes_das_8_fora():
    assert jc.dentro_da_janela_consigup(_dt(7, 59)) is False

def test_borda_16_44_dentro():
    assert jc.dentro_da_janela_consigup(_dt(16, 44)) is True

def test_borda_16_45_fora():  # margem de 15 min antes das 17h
    assert jc.dentro_da_janela_consigup(_dt(16, 45)) is False

def test_apos_17_fora():
    assert jc.dentro_da_janela_consigup(_dt(18, 30)) is False

def test_sabado_fora():  # 2026-06-27 = sábado
    assert jc.dentro_da_janela_consigup(datetime(2026, 6, 27, 14, 0)) is False

def test_domingo_fora():  # 2026-06-28 = domingo
    assert jc.dentro_da_janela_consigup(datetime(2026, 6, 28, 14, 0)) is False

def test_status_enum_fora_janela():
    from app.core.enums import CollectionStatus
    assert CollectionStatus.FORA_JANELA == "fora_janela"
