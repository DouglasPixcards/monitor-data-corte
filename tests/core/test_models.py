from app.core.models import Execucao, DadoCorte, Evento


def test_execucao_fields():
    e = Execucao(
        id="abc",
        processadora="consigfacil",
        executada_em="2026-04-29T08:00:00",
        status="ok",
        total_convenios=3,
        success_count=3,
        error_count=0,
    )
    assert e.id == "abc"
    assert e.processadora == "consigfacil"
    assert e.status == "ok"
    assert e.total_convenios == 3


def test_dado_corte_campos_opcionais_podem_ser_none():
    d = DadoCorte(
        id="d1",
        execucao_id="exec1",
        convenio_key="belterra",
        convenio_nome=None,
        folha=None,
        mes_atual=None,
        data_corte=None,
        coletado_em="2026-04-29T08:00:00",
    )
    assert d.folha is None
    assert d.data_corte is None


def test_evento_fields_data_corte_alterada():
    e = Evento(
        id="e1",
        tipo="data_corte_alterada",
        processadora="consigfacil",
        convenio_key="belterra",
        execucao_id="exec1",
        detectado_em="2026-04-29T08:00:00",
        folha="FOLHA 02/26",
        mes_atual="02/2026",
        data_corte_anterior="10/05/2026",
        data_corte_nova="08/05/2026",
    )
    assert e.data_corte_anterior == "10/05/2026"
    assert e.data_corte_nova == "08/05/2026"


def test_evento_registro_novo_anterior_e_none():
    e = Evento(
        id="e2",
        tipo="registro_novo",
        processadora="consigfacil",
        convenio_key="belterra",
        execucao_id="exec1",
        detectado_em="2026-04-29T08:00:00",
        folha="FOLHA 02/26",
        mes_atual="02/2026",
        data_corte_anterior=None,
        data_corte_nova="10/05/2026",
    )
    assert e.data_corte_anterior is None
    assert e.data_corte_nova == "10/05/2026"
