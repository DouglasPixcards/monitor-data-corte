from app.services.comparador_service import ComparadorService
from app.core.models import DadoCorte
from app.core.enums import EventoTipo


def _dado(convenio_key: str, folha: str, mes_atual: str, data_corte: str, execucao_id: str = "exec1") -> DadoCorte:
    return DadoCorte(
        id="id", execucao_id=execucao_id, convenio_key=convenio_key,
        convenio_nome=None, folha=folha, mes_atual=mes_atual,
        data_corte=data_corte, coletado_em="2026-04-29T08:00:00",
    )


def test_detecta_mudanca_de_data():
    anterior = [_dado("belterra", "FOLHA 02", "02/2026", "10/05/2026")]
    atual = [_dado("belterra", "FOLHA 02", "02/2026", "08/05/2026")]
    eventos = ComparadorService().comparar("consigfacil", "exec2", anterior, atual)
    assert len(eventos) == 1
    assert eventos[0].tipo == EventoTipo.DATA_CORTE_ALTERADA
    assert eventos[0].data_corte_anterior == "10/05/2026"
    assert eventos[0].data_corte_nova == "08/05/2026"
    assert eventos[0].convenio_key == "belterra"


def test_sem_mudanca_nao_gera_evento():
    anterior = [_dado("belterra", "FOLHA 02", "02/2026", "10/05/2026")]
    atual = [_dado("belterra", "FOLHA 02", "02/2026", "10/05/2026")]
    eventos = ComparadorService().comparar("consigfacil", "exec2", anterior, atual)
    assert eventos == []


def test_detecta_registro_novo():
    anterior = []
    atual = [_dado("belterra", "FOLHA 02", "02/2026", "10/05/2026")]
    eventos = ComparadorService().comparar("consigfacil", "exec2", anterior, atual)
    assert len(eventos) == 1
    assert eventos[0].tipo == EventoTipo.REGISTRO_NOVO
    assert eventos[0].data_corte_anterior is None
    assert eventos[0].data_corte_nova == "10/05/2026"


def test_detecta_registro_nao_encontrado():
    anterior = [_dado("belterra", "FOLHA 02", "02/2026", "10/05/2026")]
    atual = []
    eventos = ComparadorService().comparar("consigfacil", "exec2", anterior, atual)
    assert len(eventos) == 1
    assert eventos[0].tipo == EventoTipo.REGISTRO_NAO_ENCONTRADO
    assert eventos[0].data_corte_anterior == "10/05/2026"
    assert eventos[0].data_corte_nova is None


def test_primeira_execucao_gera_apenas_registros_novos():
    atual = [
        _dado("belterra", "FOLHA 02", "02/2026", "10/05/2026"),
        _dado("maranhao", "FOLHA 02", "02/2026", "12/05/2026"),
    ]
    eventos = ComparadorService().comparar("consigfacil", "exec1", [], atual)
    assert len(eventos) == 2
    assert all(e.tipo == EventoTipo.REGISTRO_NOVO for e in eventos)


def test_chave_inclui_convenio_key_para_evitar_colisao():
    # belterra e maranhao com mesma folha+mes mas dados corte diferentes
    anterior = [
        _dado("belterra", "FOLHA 02", "02/2026", "10/05/2026"),
        _dado("maranhao", "FOLHA 02", "02/2026", "12/05/2026"),
    ]
    atual = [
        _dado("belterra", "FOLHA 02", "02/2026", "10/05/2026"),  # sem mudança
        _dado("maranhao", "FOLHA 02", "02/2026", "09/05/2026"),  # mudou
    ]
    eventos = ComparadorService().comparar("consigfacil", "exec2", anterior, atual)
    assert len(eventos) == 1
    assert eventos[0].tipo == EventoTipo.DATA_CORTE_ALTERADA
    assert eventos[0].convenio_key == "maranhao"
