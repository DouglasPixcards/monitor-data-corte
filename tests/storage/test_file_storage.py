import json
from pathlib import Path

import pytest
from app.core.models import Execucao, DadoCorte, Evento
from app.storage.file_storage import (
    FileExecucaoRepository,
    FileDadosCorteRepository,
    FileEventoRepository,
)


@pytest.fixture
def base(tmp_path):
    return str(tmp_path)


# --- ExecucaoRepository ---

def test_execucao_salvar_e_listar(base):
    repo = FileExecucaoRepository(base)
    e = Execucao(
        id="exec1", processadora="consigfacil",
        executada_em="2026-04-29T08:00:00", status="ok",
        total_convenios=3, success_count=3, error_count=0,
    )
    repo.salvar(e)
    resultado = repo.listar("consigfacil")
    assert len(resultado) == 1
    assert resultado[0].id == "exec1"
    assert resultado[0].status == "ok"


def test_buscar_ultima_ok_retorna_none_se_vazio(base):
    repo = FileExecucaoRepository(base)
    assert repo.buscar_ultima_ok("consigfacil") is None


def test_buscar_ultima_ok_ignora_execucoes_com_erro(base):
    repo = FileExecucaoRepository(base)
    e_ok = Execucao(
        id="exec1", processadora="consigfacil",
        executada_em="2026-04-29T07:00:00", status="ok",
        total_convenios=3, success_count=3, error_count=0,
    )
    e_erro = Execucao(
        id="exec2", processadora="consigfacil",
        executada_em="2026-04-29T08:00:00", status="erro",
        total_convenios=3, success_count=0, error_count=3,
    )
    repo.salvar(e_ok)
    repo.salvar(e_erro)
    ultima = repo.buscar_ultima_ok("consigfacil")
    assert ultima is not None
    assert ultima.id == "exec1"


def test_listar_ordena_mais_recente_primeiro(base):
    repo = FileExecucaoRepository(base)
    repo.salvar(Execucao(
        id="exec1", processadora="consigfacil",
        executada_em="2026-04-28T08:00:00", status="ok",
        total_convenios=1, success_count=1, error_count=0,
    ))
    repo.salvar(Execucao(
        id="exec2", processadora="consigfacil",
        executada_em="2026-04-29T08:00:00", status="ok",
        total_convenios=1, success_count=1, error_count=0,
    ))
    resultado = repo.listar("consigfacil")
    assert resultado[0].id == "exec2"


# --- DadosCorteRepository ---

def test_dados_corte_salvar_e_buscar(base):
    repo = FileDadosCorteRepository(base)
    dados = [
        DadoCorte(
            id="d1", execucao_id="exec1", convenio_key="belterra",
            convenio_nome="Belterra", folha="FOLHA 02", mes_atual="02/2026",
            data_corte="10/05/2026", coletado_em="2026-04-29T08:00:00",
        ),
    ]
    repo.salvar_lote(dados)
    resultado = repo.buscar_por_execucao("exec1")
    assert len(resultado) == 1
    assert resultado[0].data_corte == "10/05/2026"
    assert resultado[0].convenio_key == "belterra"


def test_dados_corte_buscar_inexistente_retorna_lista_vazia(base):
    repo = FileDadosCorteRepository(base)
    assert repo.buscar_por_execucao("nao-existe") == []


def test_dados_corte_salvar_lote_vazio_nao_falha(base):
    repo = FileDadosCorteRepository(base)
    repo.salvar_lote([])  # não deve levantar exceção


# --- EventoRepository ---

def test_evento_salvar_lote(base):
    repo = FileEventoRepository(base)
    eventos = [
        Evento(
            id="e1", tipo="data_corte_alterada", processadora="consigfacil",
            convenio_key="belterra", execucao_id="exec1",
            detectado_em="2026-04-29T08:00:00", folha="FOLHA 02",
            mes_atual="02/2026", data_corte_anterior="10/05/2026",
            data_corte_nova="08/05/2026",
        ),
    ]
    repo.salvar_lote(eventos)
    arquivos = list(Path(base).rglob("*.jsonl"))
    assert len(arquivos) == 1
    linha = json.loads(arquivos[0].read_text(encoding="utf-8").strip())
    assert linha["id"] == "e1"
    assert linha["convenio_key"] == "belterra"
    assert linha["data_corte_anterior"] == "10/05/2026"


def test_evento_salvar_lote_vazio_nao_falha(base):
    repo = FileEventoRepository(base)
    repo.salvar_lote([])
