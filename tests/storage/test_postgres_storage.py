"""Testes de paridade do backend Postgres com o file storage.

Espelham os cenários de test_file_storage.py contra os PostgresRepositories.

- Pulam automaticamente (importorskip) se SQLAlchemy/psycopg não estiverem
  instalados (ex: ambiente local sem deps de DB).
- Pulam se não houver um Postgres acessível via TEST_DATABASE_URL ou DATABASE_URL.

No container: `docker compose run --rm runner pytest tests/storage/test_postgres_storage.py`
"""
import os

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("psycopg")

from sqlalchemy import create_engine, text

from app.core.models import DadoCorte, Evento, Execucao
from app.core.settings import settings
from app.storage import db as db_module
from app.storage.sql_models import Base

# Banco a usar nos testes. Pode ser o mesmo do compose — a fixture isola TUDO
# num schema descartável (paridade_test), então NUNCA toca o schema `public`
# onde ficam os dados reais.
_BASE_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
_TEST_SCHEMA = "paridade_test"


def _url_com_schema(url: str, schema: str) -> str:
    """Acrescenta search_path=schema à connection string (psycopg `options`)."""
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}options=-csearch_path%3D{schema}"


@pytest.fixture
def pg_repos():
    if not _BASE_URL:
        pytest.skip("TEST_DATABASE_URL/DATABASE_URL não configurada")

    admin = create_engine(_BASE_URL)
    try:
        with admin.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres indisponível: {e}")

    # Schema isolado e limpo — recriado a cada teste, jamais toca o `public`.
    with admin.begin() as c:
        c.execute(text(f"DROP SCHEMA IF EXISTS {_TEST_SCHEMA} CASCADE"))
        c.execute(text(f"CREATE SCHEMA {_TEST_SCHEMA}"))

    # Aponta a engine global (db.py) para o schema de teste.
    settings.DATABASE_URL = _url_com_schema(_BASE_URL, _TEST_SCHEMA)
    db_module._engine = None
    db_module._SessionLocal = None
    engine = db_module.get_engine()
    Base.metadata.create_all(engine)

    from app.storage.postgres_storage import (
        PostgresDadosCorteRepository,
        PostgresEventoRepository,
        PostgresExecucaoRepository,
    )
    try:
        yield (
            PostgresExecucaoRepository(),
            PostgresDadosCorteRepository(),
            PostgresEventoRepository(),
        )
    finally:
        # Remove apenas o schema de teste; o `public` (produção) fica intacto.
        db_module._engine = None
        db_module._SessionLocal = None
        with admin.begin() as c:
            c.execute(text(f"DROP SCHEMA IF EXISTS {_TEST_SCHEMA} CASCADE"))
        admin.dispose()


# --- ExecucaoRepository ---

def test_execucao_salvar_e_listar(pg_repos):
    repo, _, _ = pg_repos
    repo.salvar(Execucao(
        id="exec1", processadora="consigfacil",
        executada_em="2026-04-29T08:00:00", status="ok",
        total_convenios=3, success_count=3, error_count=0,
    ))
    resultado = repo.listar("consigfacil")
    assert len(resultado) == 1
    assert resultado[0].id == "exec1"
    assert resultado[0].status == "ok"


def test_buscar_ultima_ok_retorna_none_se_vazio(pg_repos):
    repo, _, _ = pg_repos
    assert repo.buscar_ultima_ok("consigfacil") is None


def test_buscar_ultima_ok_ignora_execucoes_com_erro(pg_repos):
    repo, _, _ = pg_repos
    repo.salvar(Execucao(
        id="exec1", processadora="consigfacil",
        executada_em="2026-04-29T07:00:00", status="ok",
        total_convenios=3, success_count=3, error_count=0,
    ))
    repo.salvar(Execucao(
        id="exec2", processadora="consigfacil",
        executada_em="2026-04-29T08:00:00", status="erro",
        total_convenios=3, success_count=0, error_count=3,
    ))
    ultima = repo.buscar_ultima_ok("consigfacil")
    assert ultima is not None
    assert ultima.id == "exec1"


def test_listar_ordena_mais_recente_primeiro(pg_repos):
    repo, _, _ = pg_repos
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

def test_dados_corte_salvar_e_buscar(pg_repos):
    _, repo, _ = pg_repos
    repo.salvar_lote([
        DadoCorte(
            id="d1", execucao_id="exec1", convenio_key="belterra",
            convenio_nome="Belterra", folha="FOLHA 02", mes_atual="02/2026",
            data_corte="10/05/2026", coletado_em="2026-04-29T08:00:00",
        ),
    ])
    resultado = repo.buscar_por_execucao("exec1")
    assert len(resultado) == 1
    assert resultado[0].data_corte == "10/05/2026"
    assert resultado[0].convenio_key == "belterra"


def test_dados_corte_buscar_inexistente_retorna_lista_vazia(pg_repos):
    _, repo, _ = pg_repos
    assert repo.buscar_por_execucao("nao-existe") == []


def test_dados_corte_salvar_lote_vazio_nao_falha(pg_repos):
    _, repo, _ = pg_repos
    repo.salvar_lote([])


def test_dados_corte_fail_fast_em_execucao_duplicada(pg_repos):
    _, repo, _ = pg_repos
    dado = DadoCorte(
        id="d1", execucao_id="exec1", convenio_key="belterra",
        coletado_em="2026-04-29T08:00:00", data_corte="10/05/2026",
    )
    repo.salvar_lote([dado])
    with pytest.raises(FileExistsError):
        repo.salvar_lote([DadoCorte(
            id="d2", execucao_id="exec1", convenio_key="belterra",
            coletado_em="2026-04-29T09:00:00", data_corte="11/05/2026",
        )])


# --- EventoRepository ---

def test_evento_salvar_lote(pg_repos):
    _, _, repo = pg_repos
    repo.salvar_lote([
        Evento(
            id="e1", tipo="data_corte_alterada", processadora="consigfacil",
            convenio_key="belterra", execucao_id="exec1",
            detectado_em="2026-04-29T08:00:00", folha="FOLHA 02",
            mes_atual="02/2026", data_corte_anterior="10/05/2026",
            data_corte_nova="08/05/2026",
        ),
    ])
    eventos = repo.listar("consigfacil", dias=3650)
    assert len(eventos) == 1
    assert eventos[0].id == "e1"
    assert eventos[0].convenio_key == "belterra"
    assert eventos[0].data_corte_anterior == "10/05/2026"
    assert eventos[0].tipo == "data_corte_alterada"


def test_evento_salvar_lote_vazio_nao_falha(pg_repos):
    _, _, repo = pg_repos
    repo.salvar_lote([])
