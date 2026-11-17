"""v1.8.3 (D49): tarefa não terminada vai para o outro dia em vez de duplicar, com rastro no dia antigo."""

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

BACKEND = Path(__file__).resolve().parents[1]


def _post(client, day, label, **kw):
    return client.post("/api/learning/checklist", json={"day": day, "label": label, **kw}).json()


def _hist(client, day):
    return {d["day"]: d for d in client.get("/api/learning/checklist/history", params={"day": day}).json()}


def test_carry_moves_task_and_leaves_a_trail(client):
    old = _post(client, "2026-11-15", "Concluir Tema 4 e Tema 5 · Engenharia de Requisitos")
    _post(client, "2026-11-15", "Concluir Tema 3 e Tema 4 · Engenharia de Requisitos")
    client.patch(f"/api/learning/checklist/{old['id'] + 1}", json={"done": True})

    assert client.post("/api/learning/checklist/carry", params={"day": "2026-11-16"}).json()["added"] == 1
    # Não volta como pendente de novo (antes ficava aberta no dia 15 e parecia duplicada)
    assert client.get("/api/learning/checklist/pending", params={"day": "2026-11-16"}).json() == []

    today = client.get("/api/learning/checklist", params={"day": "2026-11-16"}).json()
    client.patch(f"/api/learning/checklist/{today[0]['id']}", json={"done": True})
    hist = _hist(client, "2026-11-16")
    d15, d16 = hist["2026-11-15"], hist["2026-11-16"]
    # Dia 15: a passada não conta como não feita
    assert (d15["done"], d15["total"], d15["carried"]) == (1, 1, 1)
    moved = next(t for t in d15["tasks"] if t["label"].startswith("Concluir Tema 4"))
    assert moved["carried_to"] == "2026-11-16" and not moved["done"]
    # Dia 16: feita, começou no dia 15
    assert (d16["done"], d16["total"]) == (1, 1)
    assert d16["tasks"][0]["started_on"] == "2026-11-15"


def test_same_task_added_by_hand_or_by_plan_also_moves(client):
    _post(client, "2026-11-12", "Ler o capítulo 2")
    _post(client, "2026-11-13", "Ler o capítulo 2")
    _post(client, "2026-11-14", "Ler o capítulo 2")
    hist = _hist(client, "2026-11-14")
    assert hist["2026-11-12"]["tasks"][0]["carried_to"] == "2026-11-13"
    assert hist["2026-11-13"]["tasks"][0]["carried_to"] == "2026-11-14"
    # A cadeia mostra o primeiro dia
    assert hist["2026-11-14"]["tasks"][0]["started_on"] == "2026-11-12"


def test_deleting_the_moved_copy_brings_the_old_task_back(client):
    _post(client, "2026-11-15", "Ler o capítulo 2")
    new = _post(client, "2026-11-16", "Ler o capítulo 2")
    assert client.get("/api/learning/checklist/pending", params={"day": "2026-11-16"}).json() == []
    client.delete(f"/api/learning/checklist/{new['id']}")
    pending = client.get("/api/learning/checklist/pending", params={"day": "2026-11-16"}).json()
    assert [(p["day"], p["carried_to"]) for p in pending] == [("2026-11-15", None)]


def test_migration_links_past_duplicates_and_backs_up(db_path):
    """O passado já duplicado é corrigido na subida (com cópia do banco antes); nada é apagado."""
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    command.upgrade(cfg, "f2c8e1a7b934")
    con = sqlite3.connect(db_path)
    rows = [("2026-11-10", "Concluir Tema 1 e Tema 2", 0), ("2026-11-12", "Concluir Tema 1 e Tema 2", 0),
            ("2026-11-13", "Concluir Tema 1 e Tema 2", 0), ("2026-11-14", "Concluir Tema 1 e Tema 2", 1),
            ("2026-11-15", "Concluir Tema 4 e Tema 5", 0), ("2026-11-16", "Concluir Tema 4 e Tema 5", 1),
            ("2026-11-14", "Ler o capítulo 2", 0)]
    for i, (day, label, done) in enumerate(rows, 1):
        con.execute("INSERT INTO checklist_item (id, day, label, done, position, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, 0, '2026-11-16', '2026-11-16')", (i, day, label, done))
    con.commit()
    con.close()

    command.upgrade(cfg, "head")
    con = sqlite3.connect(db_path)
    got = dict(con.execute("SELECT id, carried_to FROM checklist_item").fetchall())
    count = con.execute("SELECT count(*) FROM checklist_item").fetchone()[0]
    con.close()
    assert got == {1: "2026-11-12", 2: "2026-11-13", 3: "2026-11-14", 4: None, 5: "2026-11-16", 6: None, 7: None}
    assert count == len(rows)
    backup = Path(db_path).parent / "backups" / f"{Path(db_path).stem}-antes-v1.8.3.db"
    assert backup.exists()
    con = sqlite3.connect(backup)
    assert con.execute("SELECT count(*) FROM checklist_item").fetchone()[0] == len(rows)
    con.close()
