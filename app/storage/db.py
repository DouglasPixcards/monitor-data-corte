"""Engine e sessão SQLAlchemy para o backend PostgreSQL.

Lazy/singleton: a engine só é criada na primeira vez que um repositório
Postgres precisa dela. Mantém o backend `file` totalmente desacoplado — quem
nunca usa Postgres não paga o custo de criar a engine nem exige DATABASE_URL.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import settings

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        if not settings.DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL não configurada — STORAGE_BACKEND=postgres exige DATABASE_URL "
                "(ex: postgresql+psycopg://user:senha@db:5432/monitor)."
            )
        _engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
    return _engine


def get_sessionmaker() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    """Sessão transacional: commit no sucesso, rollback em exceção, sempre fecha."""
    factory = get_sessionmaker()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _alembic_head() -> str | None:
    """A revisão HEAD das migrations (do disco, sem tocar o banco)."""
    from pathlib import Path

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    return ScriptDirectory.from_config(cfg).get_current_head()


def assert_ready() -> None:
    """Falha CEDO e claro se o Postgres não está pronto — chame no startup quando
    STORAGE_BACKEND=postgres. Caso contrário a falha só apareceria na 1ª query,
    podendo derrubar silenciosamente uma coleta agendada.

    Verifica: DATABASE_URL configurada (via get_engine), banco acessível, e schema
    aplicado até a HEAD do Alembic (não só migrado parcialmente).
    """
    from sqlalchemy import text

    engine = get_engine()  # RuntimeError claro se DATABASE_URL vazia
    try:
        with engine.connect() as conn:
            db_rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(
            "Postgres inacessível ou schema não migrado — rode `alembic upgrade head` "
            f"antes de iniciar com STORAGE_BACKEND=postgres. Detalhe: {e}"
        ) from e

    head = _alembic_head()
    if db_rev != head:
        raise RuntimeError(
            f"Schema Postgres desatualizado (alembic_version={db_rev!r}, esperado head={head!r}). "
            "Rode `alembic upgrade head`."
        )
