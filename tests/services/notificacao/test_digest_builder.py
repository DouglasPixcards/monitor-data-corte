from app.services.notificacao.digest_builder import DigestBuilder
from app.core.models import Evento
from app.core.enums import EventoTipo


def _mudanca(convenio_key: str, antes: str, depois: str) -> Evento:
    return Evento(
        id="e1",
        tipo=EventoTipo.DATA_CORTE_ALTERADA,
        processadora="consigfacil",
        convenio_key=convenio_key,
        execucao_id="exec1",
        detectado_em="2026-04-29T08:00:00",
        folha="FOLHA 02/26",
        mes_atual="02/2026",
        data_corte_anterior=antes,
        data_corte_nova=depois,
    )


def test_assunto_singular():
    assunto, _ = DigestBuilder.build("consigfacil", [_mudanca("belterra", "10/05/2026", "08/05/2026")])
    assert "1 alteração" in assunto
    assert "consigfacil" in assunto


def test_assunto_plural():
    mudancas = [
        _mudanca("belterra", "10/05/2026", "08/05/2026"),
        _mudanca("maranhao", "12/05/2026", "10/05/2026"),
    ]
    assunto, _ = DigestBuilder.build("consigfacil", mudancas)
    assert "2 alterações" in assunto


def test_corpo_contem_dados_da_mudanca():
    mudancas = [_mudanca("belterra", "10/05/2026", "08/05/2026")]
    _, corpo = DigestBuilder.build("consigfacil", mudancas)
    assert "belterra" in corpo
    assert "10/05/2026" in corpo
    assert "08/05/2026" in corpo


def test_corpo_e_html():
    _, corpo = DigestBuilder.build("consigfacil", [_mudanca("b", "x", "y")])
    assert "<html" in corpo.lower() or "<table" in corpo.lower()
