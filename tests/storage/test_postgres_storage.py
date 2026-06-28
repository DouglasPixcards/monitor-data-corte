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


def test_buscar_por_execucao_ordem_deterministica(pg_repos):
    # Sem ORDER BY a ordem das linhas é arbitrária no Postgres; garantimos
    # determinismo por convenio_key (evita diffs instáveis em /cortes/atuais).
    _, repo, _ = pg_repos
    repo.salvar_lote([
        DadoCorte(id="d3", execucao_id="e1", convenio_key="zeta", coletado_em="2026-04-29T08:00:00"),
        DadoCorte(id="d1", execucao_id="e1", convenio_key="alfa", coletado_em="2026-04-29T08:00:00"),
        DadoCorte(id="d2", execucao_id="e1", convenio_key="beta", coletado_em="2026-04-29T08:00:00"),
    ])
    res = repo.buscar_por_execucao("e1")
    assert [d.convenio_key for d in res] == ["alfa", "beta", "zeta"]


def test_dados_corte_aceita_multiplas_folhas_por_convenio(pg_repos):
    # Um convênio pode ter VÁRIAS folhas/órgãos na mesma execução — NÃO há
    # uniqueness composta; ambas as linhas devem ser preservadas.
    _, repo, _ = pg_repos
    repo.salvar_lote([
        DadoCorte(id="d1", execucao_id="e1", convenio_key="cuiaba", folha="Cuiabá Prev",
                  coletado_em="2026-04-29T08:00:00", data_corte="10/06/2026"),
        DadoCorte(id="d2", execucao_id="e1", convenio_key="cuiaba", folha="Prefeitura de Cuiabá",
                  coletado_em="2026-04-29T08:00:00", data_corte="10/06/2026"),
    ])
    res = repo.buscar_por_execucao("e1")
    assert len(res) == 2
    assert {d.folha for d in res} == {"Cuiabá Prev", "Prefeitura de Cuiabá"}


def test_buscar_por_execucao_tiebreaker_por_id(pg_repos):
    # Mesmo convenio_key (multi-folha): o desempate da ordenação é por id
    # (trava o `, id` no ORDER BY — sem ele a ordem entre folhas seria arbitrária).
    _, repo, _ = pg_repos
    repo.salvar_lote([
        DadoCorte(id="b", execucao_id="e1", convenio_key="cuiaba", folha="F2",
                  coletado_em="2026-04-29T08:00:00"),
        DadoCorte(id="a", execucao_id="e1", convenio_key="cuiaba", folha="F1",
                  coletado_em="2026-04-29T08:00:00"),
    ])
    res = repo.buscar_por_execucao("e1")
    assert [d.id for d in res] == ["a", "b"]  # por id, não ordem de inserção


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


# --- db.assert_ready (fail-fast no startup) ---

def test_alembic_head_e_a_ultima_revisao():
    # Roda mesmo sem Postgres (não usa a fixture) — guarda de drift da HEAD.
    from app.storage.db import _alembic_head
    assert _alembic_head() == "0002_evento_falha_campos"


def test_assert_ready_falha_se_schema_nao_migrado(pg_repos):
    # A fixture cria as tabelas via create_all, mas NÃO cria alembic_version →
    # assert_ready deve falhar claro (schema não está na head das migrations).
    from app.storage.db import assert_ready
    with pytest.raises(RuntimeError, match="alembic upgrade head"):
        assert_ready()


def test_assert_ready_ok_quando_na_head(pg_repos):
    from sqlalchemy import text

    from app.storage import db as db_module
    from app.storage.db import _alembic_head, assert_ready

    eng = db_module.get_engine()
    with eng.begin() as c:
        c.execute(text("CREATE TABLE alembic_version (version_num varchar(64) NOT NULL)"))
        c.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:v)"),
            {"v": _alembic_head()},
        )
    assert_ready()  # não levanta


def test_assert_ready_falha_se_schema_atras_da_head(pg_repos):
    # alembic_version existe mas numa revisão ANTIGA (atrás da head) → falha
    # claro (o ponto-chave do assert_ready vs um ping de conexão simples).
    from sqlalchemy import text

    from app.storage import db as db_module
    from app.storage.db import assert_ready

    eng = db_module.get_engine()
    with eng.begin() as c:
        c.execute(text("CREATE TABLE alembic_version (version_num varchar(64) NOT NULL)"))
        c.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0001_inicial')"))
    with pytest.raises(RuntimeError, match="desatualizado"):
        assert_ready()
