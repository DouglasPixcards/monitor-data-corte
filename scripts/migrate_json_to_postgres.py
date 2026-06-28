"""migrate_json_to_postgres.py — Backfill the existing JSON corpus into Postgres.

Idempotent: re-running inserts nothing new (ON CONFLICT DO NOTHING on the
primary key `id`). There is no composite unique key — a convênio can have
multiple folhas/órgãos per execução, so those are distinct rows preserved as-is.

Usage (CLI):
    python scripts/migrate_json_to_postgres.py [--source DIR] [--dry-run]

Programmatic usage:
    from scripts.migrate_json_to_postgres import migrar
    summary = migrar("/path/to/data", dry_run=False)

Return value (dict):
    {
        "execucoes":   {"read": int, "inserted": int, "skipped_existing": int, "malformed": int},
        "dados_corte": {"read": int, "inserted": int, "skipped_existing": int, "malformed": int},
        "eventos":     {"read": int, "inserted": int, "skipped_existing": int, "malformed": int,
                        "missing_tipo": int},
    }

On --dry-run, "inserted" holds the would-insert count and NOTHING is written to the
DB. Atenção: o dry-run é um TETO otimista — não consulta o banco, então ignora as
linhas que já existem (numa re-execução, o "would-insert" superestima o que de fato
seria inserido). O número real de inseridos só sai na execução de verdade.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Permite rodar como script (`python scripts/migrate_json_to_postgres.py`):
# garante o repo root no sys.path para importar `app`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402

from app.core.settings import settings  # noqa: E402
from app.storage import db as db_module  # noqa: E402
from app.storage.sql_models import DadoCorteRow, EventoRow, ExecucaoRow  # noqa: E402


# ---------------------------------------------------------------------------
# Collectors — read JSON/JSONL files defensively (skip malformed, never raise)
# ---------------------------------------------------------------------------

def _collect_execucoes(source: Path) -> tuple[list[dict], int]:
    """Walk {source}/processadoras/*/execucoes/*.json.

    Returns (rows, malformed_count).
    """
    rows: list[dict] = []
    malformed = 0
    procs_dir = source / "processadoras"
    if not procs_dir.exists():
        return rows, malformed

    for execucoes_dir in procs_dir.glob("*/execucoes"):
        for f in execucoes_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                rows.append({
                    "id": data["id"],
                    "processadora": data["processadora"],
                    "executada_em": data["executada_em"],
                    "status": data["status"],
                    "total_convenios": int(data["total_convenios"]),
                    "success_count": int(data["success_count"]),
                    "error_count": int(data["error_count"]),
                    "erros": data.get("erros", []),
                })
            except (json.JSONDecodeError, TypeError, KeyError, ValueError):
                malformed += 1

    return rows, malformed


def _collect_dados_corte(source: Path) -> tuple[list[dict], int]:
    """Walk {source}/dados_corte/*.json (each file is a JSON array).

    Returns (rows, malformed_count).
    """
    rows: list[dict] = []
    malformed = 0
    dados_dir = source / "dados_corte"
    if not dados_dir.exists():
        return rows, malformed

    for f in dados_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, TypeError):
            malformed += 1
            continue

        if not isinstance(data, list):
            malformed += 1
            continue

        for item in data:
            try:
                rows.append({
                    "id": item["id"],
                    "execucao_id": item["execucao_id"],
                    "convenio_key": item["convenio_key"],
                    "coletado_em": item["coletado_em"],
                    "convenio_nome": item.get("convenio_nome"),
                    "folha": item.get("folha"),
                    "mes_atual": item.get("mes_atual"),
                    "data_corte": item.get("data_corte"),
                })
            except (TypeError, KeyError):
                malformed += 1

    return rows, malformed


def _collect_eventos(source: Path) -> tuple[list[dict], int, int]:
    """Walk {source}/processadoras/*/eventos/*.jsonl (one JSON object per line).

    Returns (rows, malformed_count, missing_tipo_count).
    Old events missing the "tipo" key default to "" and are counted separately.
    """
    rows: list[dict] = []
    malformed = 0
    missing_tipo = 0
    procs_dir = source / "processadoras"
    if not procs_dir.exists():
        return rows, malformed, missing_tipo

    for eventos_dir in procs_dir.glob("*/eventos"):
        for f in eventos_dir.glob("*.jsonl"):
            try:
                lines = f.read_text(encoding="utf-8").splitlines()
            except OSError:
                malformed += 1
                continue

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    # `.get(...) or ""` cobre chave ausente E "tipo": null explícito
                    # (a coluna é NOT NULL). Conta missing_tipo só após o append, pra
                    # uma linha sem 'id' (KeyError) não ser contada em dobro.
                    tipo = data.get("tipo") or ""
                    rows.append({
                        "id": data["id"],
                        "tipo": tipo,
                        "processadora": data["processadora"],
                        "convenio_key": data["convenio_key"],
                        "execucao_id": data["execucao_id"],
                        "detectado_em": data["detectado_em"],
                        "folha": data.get("folha"),
                        "mes_atual": data.get("mes_atual"),
                        "data_corte_anterior": data.get("data_corte_anterior"),
                        "data_corte_nova": data.get("data_corte_nova"),
                        "categoria": data.get("categoria"),
                        "subtipo": data.get("subtipo"),
                        "detalhe": data.get("detalhe"),
                    })
                    if not tipo:
                        missing_tipo += 1
                except (json.JSONDecodeError, TypeError, KeyError):
                    malformed += 1

    return rows, malformed, missing_tipo


# ---------------------------------------------------------------------------
# Core migration logic
# ---------------------------------------------------------------------------

# Insere em lotes: rows*colunas precisa ficar abaixo do teto de 65535 parâmetros
# por statement do Postgres. eventos tem 13 colunas → 1000*13=13000, com folga.
_CHUNK = 1000


def _do_insert(session: Any, table_cls: Any, rows: list[dict]) -> tuple[int, int]:
    """Insert `rows` into `table_cls` with ON CONFLICT DO NOTHING, em lotes.

    Uses RETURNING to get the exact count of rows actually inserted, because
    psycopg v3 + SQLAlchemy 2.x does not populate result.rowcount reliably for
    INSERT … ON CONFLICT DO NOTHING statements. Chunked para não estourar o teto
    de 65535 parâmetros do Postgres num corpus grande.

    Returns (inserted, skipped_existing).
    """
    if not rows:
        return 0, 0
    inserted = 0
    for i in range(0, len(rows), _CHUNK):
        chunk = rows[i:i + _CHUNK]
        stmt = (
            pg_insert(table_cls)
            .values(chunk)
            .on_conflict_do_nothing()
            .returning(table_cls.id)
        )
        inserted += len(session.execute(stmt).fetchall())
    return inserted, len(rows) - inserted


def migrar(source: str | Path, dry_run: bool = False) -> dict[str, Any]:
    """Migrate JSON corpus under *source* to Postgres.

    Parameters
    ----------
    source:
        Root directory of the JSON corpus (default: settings.STORAGE_PATH).
    dry_run:
        If True, count rows but write nothing to the database.

    Returns
    -------
    dict
        Per-table summary of read / inserted / skipped_existing / malformed counts.
        On dry_run, "inserted" holds the would-insert count.
    """
    source = Path(source)

    # --- Collect all rows from disk (no DB access yet) ---
    exec_rows, exec_malformed = _collect_execucoes(source)
    dc_rows, dc_malformed = _collect_dados_corte(source)
    ev_rows, ev_malformed, ev_missing_tipo = _collect_eventos(source)

    if ev_missing_tipo:
        print(
            f"[AVISO] {ev_missing_tipo} evento(s) sem campo 'tipo' — "
            "será(ão) inserido(s) com tipo=''.",
            file=sys.stderr,
        )

    # --- Dry-run: report counts without touching the DB ---
    if dry_run:
        return {
            "execucoes": {
                "read": len(exec_rows) + exec_malformed,
                "inserted": len(exec_rows),
                "skipped_existing": 0,
                "malformed": exec_malformed,
            },
            "dados_corte": {
                "read": len(dc_rows) + dc_malformed,
                "inserted": len(dc_rows),
                "skipped_existing": 0,
                "malformed": dc_malformed,
            },
            "eventos": {
                "read": len(ev_rows) + ev_malformed,
                "inserted": len(ev_rows),
                "skipped_existing": 0,
                "malformed": ev_malformed,
                "missing_tipo": ev_missing_tipo,
            },
        }

    # --- Real insert ---
    with db_module.session_scope() as session:
        exec_inserted, exec_skipped = _do_insert(session, ExecucaoRow, exec_rows)
        dc_inserted, dc_skipped = _do_insert(session, DadoCorteRow, dc_rows)
        ev_inserted, ev_skipped = _do_insert(session, EventoRow, ev_rows)

    return {
        "execucoes": {
            "read": len(exec_rows) + exec_malformed,
            "inserted": exec_inserted,
            "skipped_existing": exec_skipped,
            "malformed": exec_malformed,
        },
        "dados_corte": {
            "read": len(dc_rows) + dc_malformed,
            "inserted": dc_inserted,
            "skipped_existing": dc_skipped,
            "malformed": dc_malformed,
        },
        "eventos": {
            "read": len(ev_rows) + ev_malformed,
            "inserted": ev_inserted,
            "skipped_existing": ev_skipped,
            "malformed": ev_malformed,
            "missing_tipo": ev_missing_tipo,
        },
    }


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def _print_summary(summary: dict[str, Any], dry_run: bool) -> None:
    mode = "[DRY-RUN] " if dry_run else ""
    print(f"\n{mode}Resumo da migração JSON → Postgres")
    print("-" * 50)
    for table, counts in summary.items():
        label_inserted = "would-insert" if dry_run else "inserted"
        print(f"  {table}:")
        print(f"    read           = {counts['read']}")
        print(f"    {label_inserted:<14} = {counts['inserted']}")
        if not dry_run:
            print(f"    skipped        = {counts['skipped_existing']}")
        print(f"    malformed      = {counts['malformed']}")
        if "missing_tipo" in counts:
            print(f"    missing_tipo   = {counts['missing_tipo']}")
    print("-" * 50)
    if dry_run:
        print("Modo dry-run: nenhuma escrita realizada.")
    else:
        total_inserted = sum(c["inserted"] for c in summary.values())
        print(f"Total inserido: {total_inserted} linhas.")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill JSON corpus into Postgres (idempotent)."
    )
    parser.add_argument(
        "--source",
        default=settings.STORAGE_PATH,
        help="Root directory of the JSON corpus (default: settings.STORAGE_PATH).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count rows only — no writes to the database.",
    )
    args = parser.parse_args()

    summary = migrar(args.source, dry_run=args.dry_run)
    _print_summary(summary, dry_run=args.dry_run)
    sys.exit(0)


if __name__ == "__main__":
    main()
