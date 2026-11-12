"""Conexão com o SQLite e sessão do SQLAlchemy."""

import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


def database_url() -> str:
    # O caminho do banco vem do ambiente; o padrão é ./data/painel.db (SPEC D4)
    url = os.environ.get("PAINEL_DATABASE_URL")
    if url:
        return url
    path = Path(os.environ.get("PAINEL_DB_PATH", "./data/painel.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


class Base(DeclarativeBase):
    pass


def make_engine(url: str | None = None):
    url = url or database_url()
    engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})

    if url.startswith("sqlite"):
        # SQLite só respeita chaves estrangeiras com este pragma ligado
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return engine


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
