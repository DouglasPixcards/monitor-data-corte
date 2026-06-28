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


def _ev_credencial_expirada():
    return Evento(
        id=str(uuid.uuid4()), tipo=EventoTipo.ERRO_COLETA, processadora="consiglog",
        convenio_key="cotia_sp", execucao_id="e1", detectado_em="2026-06-26T10:00:00",
        categoria="credencial_expirada", subtipo="falha_nova",
        detalhe="[ConsigLog] Autenticação falhou — Senha do usuário está expirada.",
    )


def test_credencial_expirada_destaque_acionavel_no_topo():
    lote = {"processadora": "consiglog", "total_convenios": 1, "success_count": 0,
            "convenios": [{"convenio_key": "cotia_sp", "convenio_nome": "Cotia-SP"}]}
    assunto, corpo = DigestBuilder.build("consiglog", [_ev_credencial_expirada()], lote)
    assert "Credencial expirada" in corpo
    assert assunto.startswith("[Ação]")


def test_credencial_expirada_persistente_ainda_acionavel():
    # Garante o requisito da spec: credencial expirada é AÇÃO mesmo se persistente
    # (não cai no rodapé). Uma regressão filtrando por subtipo passaria sem este teste.
    ev = Evento(
        id=str(uuid.uuid4()), tipo=EventoTipo.ERRO_COLETA, processadora="consiglog",
        convenio_key="cotia_sp", execucao_id="e1", detectado_em="2026-06-26T10:00:00",
        categoria="credencial_expirada", subtipo="persistente",
        detalhe="[ConsigLog] Senha do usuário está expirada.",
    )
    lote = {"processadora": "consiglog", "total_convenios": 1, "success_count": 0,
            "convenios": [{"convenio_key": "cotia_sp", "convenio_nome": "Cotia-SP"}]}
    assunto, corpo = DigestBuilder.build("consiglog", [ev], lote)
    assert "Credencial expirada" in corpo
    assert assunto.startswith("[Ação]")


def _ev_valor_invalido():
    return Evento(
        id=str(uuid.uuid4()), tipo=EventoTipo.ERRO_COLETA, processadora="consigfacil",
        convenio_key="belterra", execucao_id="e1", detectado_em="2026-06-27T10:00:00",
        categoria="valor_invalido", subtipo=None,
        detalhe="data_corte inválida coletada (folha='FOLHA 02'): 'ver tabela'",
    )


def test_valor_invalido_destaque_acionavel():
    lote = {"processadora": "consigfacil", "total_convenios": 1, "success_count": 0,
            "convenios": [{"convenio_key": "belterra", "convenio_nome": "Belterra"}]}
    assunto, corpo = DigestBuilder.build("consigfacil", [_ev_valor_invalido()], lote)
    assert "Valor de data inválido" in corpo
    assert assunto.startswith("[Ação]")


def _ev_salto_suspeito():
    return Evento(
        id=str(uuid.uuid4()), tipo=EventoTipo.ERRO_COLETA, processadora="consigfacil",
        convenio_key="belterra", execucao_id="e1", detectado_em="2026-06-28T10:00:00",
        categoria="salto_suspeito", subtipo=None,
        detalhe="salto grande de data_corte: '10/05/2026' → '28/06/2026'",
    )


def test_salto_suspeito_destaque_acionavel():
    lote = {"processadora": "consigfacil", "total_convenios": 1, "success_count": 1,
            "convenios": [{"convenio_key": "belterra", "convenio_nome": "Belterra"}]}
    assunto, corpo = DigestBuilder.build("consigfacil", [_ev_salto_suspeito()], lote)
    assert "Salto grande" in corpo
    assert assunto.startswith("[Ação]")
