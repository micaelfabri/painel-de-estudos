"""Cada teste roda num SQLite novo, criado pelas migrações do Alembic."""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

BACKEND = Path(__file__).resolve().parents[1]

# O TestClient usa o host "testserver"; precisa estar na lista antes de importar o app
os.environ.setdefault("PAINEL_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    monkeypatch.setenv("PAINEL_DB_PATH", str(path))
    return path


@pytest.fixture()
def client(db_path):
    from app import db as db_module

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    command.upgrade(cfg, "head")

    engine = db_module.make_engine(f"sqlite:///{db_path}")
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    from app.main import app

    def _session():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[db_module.get_session] = _session
    app.state.shuffle_options = False  # os testes sabem onde está a certa; um teste próprio liga o embaralhamento
    test_client = TestClient(app)
    test_client.session_factory = TestSession  # usado pelos testes que precisam do banco direto
    yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture()
def seeded(client):
    from app.seed import seed

    with client.session_factory() as s:
        seed(s)
    return client
