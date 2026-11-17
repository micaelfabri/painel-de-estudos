"""v1.10 (D53): tarefa de tema guarda os temas pelo id; renomear tema não duplica tarefa no "Montar o dia"."""

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

from app import models

BACKEND = Path(__file__).resolve().parents[1]
DAY = "2026-11-10"


def _plan(client):
    return client.post("/api/learning/checklist/plan", params={"day": DAY}).json()["items"]


def _study(items):
    return [i for i in items if i["label"].startswith(("Concluir ", "Estudar "))]


def test_plan_stores_topic_ids_and_renaming_does_not_duplicate(seeded):
    first = _study(_plan(seeded))
    assert len(first) == 1 and len(first[0]["topic_ids"]) == 2
    # Renomeia os temas citados (o texto da tarefa deixa de bater com os títulos)
    with seeded.session_factory() as s:
        for tid in first[0]["topic_ids"]:
            t = s.get(models.Topic, tid)
            t.title = f"Nome novo {tid}"
        s.commit()
    got = seeded.get(f"/api/learning/checklist/{first[0]['id']}/topics").json()
    assert [t["id"] for t in got] == first[0]["topic_ids"]
    assert len(_study(_plan(seeded))) == 1  # nada de tarefa nova com o nome novo


def test_old_task_without_ids_still_blocks_a_second_study_task(seeded):
    """Tarefa antiga (sem topic_ids) com texto que não bate mais: a disciplina já tem tarefa aberta hoje."""
    action = seeded.get("/api/overview", params={"today": DAY}).json()["next_action"]
    seeded.post("/api/learning/checklist", json={"day": DAY, "label": f"Concluir Tema 99 · {action['subject_name']}",
                                                 "topic_id": action["topic_id"]})
    labels = [i["label"] for i in _study(_plan(seeded))]
    assert labels == [f"Concluir Tema 99 · {action['subject_name']}"]


def test_done_task_lets_the_next_topics_in(seeded):
    """Com a tarefa de hoje feita e os temas concluídos no portal, o próximo passo entra normalmente."""
    first = _study(_plan(seeded))[0]
    seeded.patch(f"/api/learning/checklist/{first['id']}", json={"done": True})
    seeded.post(f"/api/learning/checklist/{first['id']}/topics-done")
    study = _study(_plan(seeded))
    assert len(study) == 2 and not set(study[1]["topic_ids"]) & set(first["topic_ids"])


def test_migration_fills_topic_ids(db_path):
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    command.upgrade(cfg, "b4d9e2f7a613")
    con = sqlite3.connect(db_path)
    # A tabela de temas só precisa de subject_id/title/position para a migração; as outras ficam com o padrão
    con.execute("PRAGMA foreign_keys=OFF")
    cols = {r[1]: r for r in con.execute("PRAGMA table_info(topic)")}
    for i, title in enumerate(["Camada de Modelo", "Camada de Controle", "Camada de Visão"], 1):
        values = {"id": i, "subject_id": 1, "title": title, "position": i}
        for name, (_, _, typ, notnull, default, _) in cols.items():
            if name not in values and notnull and default is None:
                values[name] = "2026-11-17" if "at" in name else (0 if "INT" in typ.upper() or "BOOL" in typ.upper() else "x")
        con.execute(f"INSERT INTO topic ({', '.join(values)}) VALUES ({', '.join('?' * len(values))})",
                    tuple(values.values()))
    rows = [(1, "Concluir Camada de Controle e Camada de Visão · Web", 2), (2, "Concluir Tema 5 · Web", 2),
            (3, "Ler o capítulo", None)]
    for item_id, label, topic_id in rows:
        con.execute("INSERT INTO checklist_item (id, day, label, topic_id, done, position, created_at, updated_at) "
                    "VALUES (?, '2026-11-17', ?, ?, 0, 0, '2026-11-17', '2026-11-17')", (item_id, label, topic_id))
    con.commit()
    con.close()
    command.upgrade(cfg, "head")
    con = sqlite3.connect(db_path)
    got = dict(con.execute("SELECT id, topic_ids FROM checklist_item").fetchall())
    con.close()
    assert got == {1: "[2, 3]", 2: "[2]", 3: None}
