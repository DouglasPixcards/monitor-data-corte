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


def test_chave_normaliza_espacos_em_folha_e_mes_atual():
    anterior = [_dado("belterra", "FOLHA 02", "02/2026", "10/05/2026")]
    atual = [_dado("belterra", " FOLHA 02 ", " 02/2026 ", "10/05/2026")]
    eventos = ComparadorService().comparar("consigfacil", "exec2", anterior, atual)
    assert eventos == []


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


# --- Camada de STATUS (falha/recuperação/gap) ---

def _status(status, erro=None, known=False, nome=None, records=1) -> dict:
    return {"status": status, "erro": erro, "known_failure": known,
            "records_count": records, "convenio_nome": nome}


def _erros(eventos):
    return [e for e in eventos if e.tipo == EventoTipo.ERRO_COLETA]


def test_status_falha_nova():
    eventos = ComparadorService().comparar(
        "consignet", "exec2", [], [],
        status_anterior={"x": "coletado"},
        status_atual={"x": _status("erro", "[X] Autenticação falhou — /auth/login")},
    )
    erro = _erros(eventos)
    assert len(erro) == 1
    assert erro[0].subtipo == "falha_nova"
    assert erro[0].categoria == "auth_falhou"
    assert "Autenticação" in erro[0].detalhe


def test_status_persistente():
    eventos = ComparadorService().comparar(
        "consignet", "exec2", [], [],
        status_anterior={"x": "falhou"},
        status_atual={"x": _status("erro", "Timeout 30000ms exceeded")},
    )
    erro = _erros(eventos)
    assert erro[0].subtipo == "persistente"
    assert erro[0].categoria == "timeout"


def test_status_recuperado():
    eventos = ComparadorService().comparar(
        "consignet", "exec2", [], [],
        status_anterior={"x": "falhou"},
        status_atual={"x": _status("ok")},
    )
    assert any(e.tipo == EventoTipo.RECUPERADO for e in eventos)
    assert _erros(eventos) == []


def test_status_gap():
    eventos = ComparadorService().comparar(
        "consignet", "exec2", [], [],
        status_anterior={"x": "coletado"},
        status_atual={},
    )
    erro = _erros(eventos)
    assert erro[0].subtipo == "gap"
    assert erro[0].categoria == "nao_executou"


def test_status_known_failure_nao_e_falha_nova():
    eventos = ComparadorService().comparar(
        "consignet", "exec2", [], [],
        status_anterior={"defensoria": "coletado"},
        status_atual={"defensoria": _status("erro", "reCAPTCHA v3", known=True)},
    )
    erro = _erros(eventos)
    assert erro[0].categoria == "falha_conhecida"
    assert erro[0].subtipo == "conhecida"


def test_status_nao_duplica_registro_nao_encontrado():
    # Convênio com dado no baseline que falhou hoje: só ERRO_COLETA, sem REGISTRO_NAO_ENCONTRADO.
    anterior = [_dado("belterra", "FOLHA 02", "02/2026", "10/05/2026")]
    eventos = ComparadorService().comparar(
        "consigfacil", "exec2", anterior, [],
        status_anterior={"belterra": "coletado"},
        status_atual={"belterra": _status("erro", "Timeout")},
    )
    tipos = {e.tipo for e in eventos}
    assert EventoTipo.REGISTRO_NAO_ENCONTRADO not in tipos
    assert EventoTipo.ERRO_COLETA in tipos


def test_sem_status_mantem_comportamento_antigo():
    # Sem os mapas de status, REGISTRO_NAO_ENCONTRADO continua sendo emitido.
    anterior = [_dado("belterra", "FOLHA 02", "02/2026", "10/05/2026")]
    eventos = ComparadorService().comparar("consigfacil", "exec2", anterior, [])
    assert len(eventos) == 1
    assert eventos[0].tipo == EventoTipo.REGISTRO_NAO_ENCONTRADO


def test_status_sem_dado_novo():
    # Coletou (status efetivo sem_dado) mas não trouxe data; antes coletava.
    eventos = ComparadorService().comparar(
        "consignet", "exec2", [], [],
        status_anterior={"x": "coletado"},
        status_atual={"x": _status("sem_dado")},
    )
    erro = _erros(eventos)
    assert erro[0].categoria == "sem_dado"
    assert erro[0].subtipo == "falha_nova"


def test_status_sem_dado_persistente():
    eventos = ComparadorService().comparar(
        "consignet", "exec2", [], [],
        status_anterior={"x": "sem_dado"},
        status_atual={"x": _status("sem_dado")},
    )
    assert _erros(eventos)[0].subtipo == "persistente"


def test_status_recuperado_de_sem_dado():
    eventos = ComparadorService().comparar(
        "consignet", "exec2", [], [],
        status_anterior={"x": "sem_dado"},
        status_atual={"x": _status("ok")},
    )
    assert any(e.tipo == EventoTipo.RECUPERADO for e in eventos)


def test_fora_janela_gera_evento_de_rodape():
    eventos = ComparadorService().comparar(
        processadora="consigup", execucao_id="e1",
        anteriores=[], atuais=[],
        status_anterior={"muana": "coletado"},
        status_atual={"muana": {"status": "fora_janela",
                                "erro": "[ConsigUp] Fora da janela de acesso (seg–sex 08:00–16:45) — coleta pulada nesta rodada.",
                                "known_failure": False, "records_count": 0,
                                "convenio_nome": "PREF DE MUANA - PA"}},
    )
    fj = [e for e in eventos if e.tipo == EventoTipo.ERRO_COLETA and e.categoria == "fora_janela"]
    assert len(fj) == 1
    assert fj[0].subtipo == "fora_janela"
