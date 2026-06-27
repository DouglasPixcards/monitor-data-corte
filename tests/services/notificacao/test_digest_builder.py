import uuid

from app.services.notification.digest_builder import DigestBuilder
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


def test_assunto_resumo_uma_mudanca():
    # Novo formato: assunto carrega a linha de resumo e marca [Ação] quando há mudança.
    assunto, _ = DigestBuilder.build("consigfacil", [_mudanca("belterra", "10/05/2026", "08/05/2026")])
    assert "1 mudanças de data" in assunto
    assert "consigfacil" in assunto
    assert assunto.startswith("[Ação]")


def test_assunto_resumo_duas_mudancas():
    mudancas = [
        _mudanca("belterra", "10/05/2026", "08/05/2026"),
        _mudanca("maranhao", "12/05/2026", "10/05/2026"),
    ]
    assunto, _ = DigestBuilder.build("consigfacil", mudancas)
    assert "2 mudanças de data" in assunto


def test_corpo_contem_dados_da_mudanca():
    mudancas = [_mudanca("belterra", "10/05/2026", "08/05/2026")]
    _, corpo = DigestBuilder.build("consigfacil", mudancas)
    assert "belterra" in corpo
    assert "10/05/2026" in corpo
    assert "08/05/2026" in corpo


def test_corpo_e_html():
    _, corpo = DigestBuilder.build("consigfacil", [_mudanca("b", "x", "y")])
    assert "<html" in corpo.lower() or "<table" in corpo.lower()


def _ev_fora_janela():
    return Evento(
        id=str(uuid.uuid4()), tipo=EventoTipo.ERRO_COLETA, processadora="consigup",
        convenio_key="muana", execucao_id="e1", detectado_em="2026-06-26T18:00:00",
        categoria="fora_janela", subtipo="fora_janela",
        detalhe="[ConsigUp] Fora da janela de acesso (seg–sex 08:00–16:45) — coleta pulada nesta rodada.",
    )


def test_fora_janela_vai_pro_rodape_sem_acao():
    lote = {"processadora": "consigup", "total_convenios": 1, "success_count": 0,
            "convenios": [{"convenio_key": "muana", "convenio_nome": "PREF DE MUANA - PA"}]}
    assunto, corpo = DigestBuilder.build("consigup", [_ev_fora_janela()], lote)
    assert "Fora da janela de acesso" in corpo
    assert not assunto.startswith("[Ação]")
