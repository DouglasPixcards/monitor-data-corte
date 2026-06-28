from app.core.enums import EventoTipo
from app.core.models import Evento, Execucao
from app.services.metricas import falhas_por_convenio, resumo_processadora


def _exec(ok, err, fora=0, em="2026-06-01T08:00:00"):
    # success_count = 'ok'; error_count = erros reais (já SEM fora_janela);
    # total_convenios inclui fora_janela. considerados (taxa) = ok + err.
    return Execucao(id="e", processadora="p", executada_em=em, status="ok",
                    total_convenios=ok + err + fora, success_count=ok, error_count=err)


def test_resumo_sem_execucoes():
    r = resumo_processadora([])
    assert r["execucoes"] == 0 and r["taxa_atual"] is None and r["tendencia"] == "sem_dados"


def test_resumo_taxa_atual_e_media():
    # listar vem DESC → recentes[0] é a "atual"
    execs = [_exec(8, 2, em="2026-06-03T08:00:00"), _exec(6, 4, em="2026-06-02T08:00:00"),
             _exec(10, 0, em="2026-06-01T08:00:00")]
    r = resumo_processadora(execs)
    assert r["taxa_atual"] == 0.8                  # 8/(8+2) da mais recente
    assert r["taxa_media"] == round(24 / 30, 4)    # (8+6+10)/(10+10+10)
    assert r["execucoes"] == 3


def test_resumo_respeita_limite():
    execs = [_exec(10, 0) for _ in range(20)]
    assert resumo_processadora(execs, limite=5)["execucoes"] == 5


def test_tendencia_melhorando():
    execs = [_exec(10, 0), _exec(10, 0), _exec(5, 5), _exec(5, 5)]  # recente melhor
    assert resumo_processadora(execs)["tendencia"] == "melhorando"


def test_tendencia_piorando():
    execs = [_exec(5, 5), _exec(5, 5), _exec(10, 0), _exec(10, 0)]  # recente pior
    assert resumo_processadora(execs)["tendencia"] == "piorando"


def test_execucao_fora_janela_nao_baixa_taxa():
    # run 100% fora_janela (considerados=0) é ignorado, não vira 0% (bug pego na revisão)
    execs = [_exec(0, 0, fora=10, em="2026-06-02T08:00:00"),  # ex.: fim de semana
             _exec(9, 1, em="2026-06-01T08:00:00")]
    r = resumo_processadora(execs)
    assert r["taxa_atual"] == 0.9   # da execução real, não 0.0 do fora-janela
    assert r["execucoes"] == 1


def test_so_fora_janela_vira_sem_dados():
    assert resumo_processadora([_exec(0, 0, fora=10)])["tendencia"] == "sem_dados"


def _erro(conv, cat="auth_falhou", sub="persistente"):
    return Evento(id="x", tipo=EventoTipo.ERRO_COLETA, processadora="p", convenio_key=conv,
                  execucao_id="e", detectado_em="2026-06-01T08:00:00", categoria=cat, subtipo=sub)


def test_falhas_conta_ignora_nao_erro_e_ordena_desc():
    eventos = [_erro("a"), _erro("a"), _erro("b"),
               Evento(id="y", tipo=EventoTipo.DATA_CORTE_ALTERADA, processadora="p",
                      convenio_key="c", execucao_id="e", detectado_em="2026-06-01T08:00:00")]
    out = falhas_por_convenio(eventos)
    assert [x["convenio_key"] for x in out] == ["a", "b"]   # 'c' não é ERRO_COLETA
    assert out[0]["falhas"] == 2
    assert out[0]["categoria"] == "auth_falhou"


def test_falhas_ignora_categorias_nao_acionaveis():
    # adiamento/gap/conhecida/qualidade não são falha de coleta acionável (bug da revisão)
    eventos = [
        _erro("real", cat="auth_falhou"),
        _erro("janela", cat="fora_janela"),
        _erro("morto", cat="falha_conhecida"),
        _erro("qual", cat="valor_invalido"),
        _erro("gap", cat="nao_executou"),
    ]
    out = falhas_por_convenio(eventos)
    assert [x["convenio_key"] for x in out] == ["real"]   # só o acionável


def test_falhas_mantem_categoria_do_mais_recente():
    # eventos vêm do mais novo p/ o antigo → mantém a categoria do primeiro visto
    eventos = [_erro("a", cat="credencial_expirada"), _erro("a", cat="auth_falhou")]
    assert falhas_por_convenio(eventos)[0]["categoria"] == "credencial_expirada"
