"""Tests for scripts/migrate_json_to_postgres.py.

Schema-isolation pattern mirrors test_postgres_storage.py:
  - Skip if TEST_DATABASE_URL / DATABASE_URL is not configured.
  - Each test runs in a throwaway schema (migrar_test); the public schema is
    never touched.
  - Schema is created fresh and dropped after each test.
"""
from __future__ import annotations

import json
import os

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("psycopg")

from sqlalchemy import create_engine, text

from app.core.settings import settings
from app.storage import db as db_module
from app.storage.sql_models import Base

_BASE_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
_TEST_SCHEMA = "migrar_test"


def _url_com_schema(url: str, schema: str) -> str:
    """Append search_path=schema to the connection string (psycopg `options`)."""
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}options=-csearch_path%3D{schema}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pg_schema():
    """Create a throwaway Postgres schema and wire db_module to it."""
    if not _BASE_URL:
        pytest.skip("TEST_DATABASE_URL/DATABASE_URL não configurada")

    admin = create_engine(_BASE_URL)
    try:
        with admin.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres indisponível: {e}")

    # Drop + recreate the test schema so every test starts clean.
    with admin.begin() as c:
        c.execute(text(f"DROP SCHEMA IF EXISTS {_TEST_SCHEMA} CASCADE"))
        c.execute(text(f"CREATE SCHEMA {_TEST_SCHEMA}"))

    # Point the global db engine at the isolated schema.
    settings.DATABASE_URL = _url_com_schema(_BASE_URL, _TEST_SCHEMA)
    db_module._engine = None
    db_module._SessionLocal = None
    engine = db_module.get_engine()
    Base.metadata.create_all(engine)

    yield  # run the test

    # Teardown: reset engine globals, then drop the test schema.
    db_module._engine = None
    db_module._SessionLocal = None
    with admin.begin() as c:
        c.execute(text(f"DROP SCHEMA IF EXISTS {_TEST_SCHEMA} CASCADE"))
    admin.dispose()


@pytest.fixture
def corpus(tmp_path):
    """Build a minimal JSON corpus on disk for migration tests.

    Layout:
      <tmp_path>/
        processadoras/testproc/execucoes/exec1.json   (1 execucao)
        dados_corte/exec1.json                         (2 dados_corte items)
        processadoras/testproc/eventos/2026-06-27.jsonl  (2 lines; 1 missing tipo)
    """
    # --- Execucao ---
    exec_dir = tmp_path / "processadoras" / "testproc" / "execucoes"
    exec_dir.mkdir(parents=True)
    (exec_dir / "exec1.json").write_text(
        json.dumps({
            "id": "exec1",
            "processadora": "testproc",
            "executada_em": "2026-06-27T08:00:00",
            "status": "ok",
            "total_convenios": 2,
            "success_count": 2,
            "error_count": 0,
            "erros": [],
        }),
        encoding="utf-8",
    )

    # --- DadoCorte (JSON array with 2 items) ---
    dc_dir = tmp_path / "dados_corte"
    dc_dir.mkdir()
    (dc_dir / "exec1.json").write_text(
        json.dumps([
            {
                "id": "dc1",
                "execucao_id": "exec1",
                "convenio_key": "conv1",
                "coletado_em": "2026-06-27T08:00:00",
                "convenio_nome": "Convenio 1",
                "folha": None,
                "mes_atual": None,
                "data_corte": None,
            },
            {
                "id": "dc2",
                "execucao_id": "exec1",
                "convenio_key": "conv2",
                "coletado_em": "2026-06-27T08:00:00",
                "convenio_nome": "Convenio 2",
                "folha": None,
                "mes_atual": None,
                "data_corte": None,
            },
        ]),
        encoding="utf-8",
    )

    # --- Eventos: 2 lines, second line is missing "tipo" ---
    ev_dir = tmp_path / "processadoras" / "testproc" / "eventos"
    ev_dir.mkdir(parents=True)
    lines = [
        json.dumps({
            "id": "ev1",
            "tipo": "data_corte_alterada",
            "processadora": "testproc",
            "convenio_key": "conv1",
            "execucao_id": "exec1",
            "detectado_em": "2026-06-27T08:00:00",
        }),
        json.dumps({
            "id": "ev2",
            # Intentionally missing "tipo" — should default to ""
            "processadora": "testproc",
            "convenio_key": "conv2",
            "execucao_id": "exec1",
            "detectado_em": "2026-06-27T08:00:01",
        }),
    ]
    (ev_dir / "2026-06-27.jsonl").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    return tmp_path


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _count_rows(table_name: str) -> int:
    """Count rows in *table_name* using the current db_module session."""
    with db_module.session_scope() as s:
        return s.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_migrar_inserts_all_rows(pg_schema, corpus):
    """First run inserts 1 execucao, 2 dados_corte, 2 eventos."""
    from scripts.migrate_json_to_postgres import migrar

    summary = migrar(corpus)

    # Summary counts
    assert summary["execucoes"]["read"] == 1
    assert summary["execucoes"]["inserted"] == 1
    assert summary["execucoes"]["skipped_existing"] == 0
    assert summary["execucoes"]["malformed"] == 0

    assert summary["dados_corte"]["read"] == 2
    assert summary["dados_corte"]["inserted"] == 2
    assert summary["dados_corte"]["skipped_existing"] == 0
    assert summary["dados_corte"]["malformed"] == 0

    assert summary["eventos"]["read"] == 2
    assert summary["eventos"]["inserted"] == 2
    assert summary["eventos"]["skipped_existing"] == 0
    assert summary["eventos"]["malformed"] == 0
    assert summary["eventos"]["missing_tipo"] == 1

    # Actual DB state
    assert _count_rows("execucoes") == 1
    assert _count_rows("dados_corte") == 2
    assert _count_rows("eventos") == 2

    # The evento that had no "tipo" was stored with tipo=''
    with db_module.session_scope() as s:
        tipo_val = s.execute(
            text("SELECT tipo FROM eventos WHERE id = 'ev2'")
        ).scalar()
    assert tipo_val == ""


def test_migrar_idempotent(pg_schema, corpus):
    """Second run inserts nothing — all rows already exist."""
    from scripts.migrate_json_to_postgres import migrar

    migrar(corpus)           # first run — populates the DB
    summary = migrar(corpus)  # second run — should skip everything

    assert summary["execucoes"]["inserted"] == 0
    assert summary["execucoes"]["skipped_existing"] == 1

    assert summary["dados_corte"]["inserted"] == 0
    assert summary["dados_corte"]["skipped_existing"] == 2

    assert summary["eventos"]["inserted"] == 0
    assert summary["eventos"]["skipped_existing"] == 2

    # Row counts must be unchanged
    assert _count_rows("execucoes") == 1
    assert _count_rows("dados_corte") == 2
    assert _count_rows("eventos") == 2


def test_migrar_dry_run_writes_nothing(pg_schema, corpus):
    """Dry-run on a fresh schema: 0 rows written, correct would-insert counts."""
    from scripts.migrate_json_to_postgres import migrar

    summary = migrar(corpus, dry_run=True)

    # Nothing written to DB
    assert _count_rows("execucoes") == 0
    assert _count_rows("dados_corte") == 0
    assert _count_rows("eventos") == 0

    # But would-insert counts are reported accurately
    assert summary["execucoes"]["inserted"] == 1
    assert summary["dados_corte"]["inserted"] == 2
    assert summary["eventos"]["inserted"] == 2
    assert summary["eventos"]["missing_tipo"] == 1


def test_migrar_tolera_malformados(pg_schema, tmp_path):
    """Arquivos/linhas malformados são pulados e contados — sem abortar a migração."""
    from scripts.migrate_json_to_postgres import migrar

    exec_dir = tmp_path / "processadoras" / "p" / "execucoes"
    exec_dir.mkdir(parents=True)
    (exec_dir / "exec1.json").write_text(json.dumps({
        "id": "exec1", "processadora": "p", "executada_em": "2026-06-27T08:00:00",
        "status": "ok", "total_convenios": 1, "success_count": 1, "error_count": 0, "erros": [],
    }), encoding="utf-8")

    # dados_corte: 1 arquivo válido + 1 que NÃO é array (malformado)
    dc_dir = tmp_path / "dados_corte"
    dc_dir.mkdir()
    (dc_dir / "exec1.json").write_text(json.dumps([
        {"id": "dc1", "execucao_id": "exec1", "convenio_key": "c1", "coletado_em": "2026-06-27T08:00:00"},
    ]), encoding="utf-8")
    (dc_dir / "exec2.json").write_text('{"nao": "e lista"}', encoding="utf-8")

    # eventos: válido / tipo=null (→ '', missing_tipo) / sem id (→ malformado) / json quebrado
    ev_dir = tmp_path / "processadoras" / "p" / "eventos"
    ev_dir.mkdir(parents=True)
    (ev_dir / "2026-06-27.jsonl").write_text("\n".join([
        json.dumps({"id": "ev1", "tipo": "x", "processadora": "p", "convenio_key": "c1",
                    "execucao_id": "exec1", "detectado_em": "2026-06-27T08:00:00"}),
        json.dumps({"id": "ev2", "tipo": None, "processadora": "p", "convenio_key": "c1",
                    "execucao_id": "exec1", "detectado_em": "2026-06-27T08:00:01"}),
        json.dumps({"tipo": "x", "processadora": "p", "convenio_key": "c1",
                    "execucao_id": "exec1", "detectado_em": "2026-06-27T08:00:02"}),
        "{ json quebrado",
    ]) + "\n", encoding="utf-8")

    summary = migrar(tmp_path)  # NÃO deve levantar

    assert summary["dados_corte"]["malformed"] == 1
    assert summary["dados_corte"]["inserted"] == 1
    assert summary["eventos"]["inserted"] == 2        # ev1 + ev2 (tipo='')
    assert summary["eventos"]["malformed"] == 2       # sem-id + json quebrado
    assert summary["eventos"]["missing_tipo"] == 1    # ev2 (tipo null → '')
    with db_module.session_scope() as s:
        assert s.execute(text("SELECT tipo FROM eventos WHERE id='ev2'")).scalar() == ""
