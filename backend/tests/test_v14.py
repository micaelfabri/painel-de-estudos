"""Testes da v1.4 (SPEC D23–D26): sessões do cronômetro, métricas, simulados, página do Notion do item."""

import json
from datetime import date

import httpx
import pytest
from alembic import command
from alembic.config import Config

from app.main import app
from tests.conftest import BACKEND


def test_timer_session_counts_pauses_and_hidden_clock(seeded):
    c = seeded
    t = c.post("/api/study/timer-sessions", json={"subject_id": 1, "started_at": "2026-11-12T10:00:00"}).json()
    # Dois trechos (duas pausas), 25 + 20 minutos ativos
    for start, secs in (("10:00:00", 1500), ("10:35:00", 1200)):
        c.post("/api/study-sessions", json={"subject_id": 1, "started_at": f"2026-11-12T{start}", "seconds": secs,
                                            "timer_session_id": t["id"]})
    c.patch(f"/api/study/timer-sessions/{t['id']}", json={"pauses": 2})
    done = c.patch(f"/api/study/timer-sessions/{t['id']}",
                   json={"end_reason": "finished", "ended_at": "2026-11-12T11:05:00"}).json()
    assert done["pauses"] == 2 and done["active_seconds"] == 2700 and done["wall_seconds"] == 3900
    assert done["end_reason"] == "finished" and done["subject_name"] == "Engenharia de Requisitos"
    # Fechar de novo não muda nada
    again = c.patch(f"/api/study/timer-sessions/{t['id']}", json={"end_reason": "reset"}).json()
    assert again["end_reason"] == "finished"
    assert c.get("/api/study/timer-sessions").json()[0]["id"] == t["id"]

    m = c.get("/api/study/metrics", params={"today": "2026-11-12", "days": 7}).json()
    assert m["timer"]["sessions"] == 1 and m["timer"]["focus"] == pytest.approx(2700 / 3900)
    assert m["totals"]["seconds"] == 2700 and m["totals"]["streak"] == 1
    assert len(m["daily"]) == 7 and m["daily"][-1]["seconds"] == 2700
    modelagem = next(s for s in m["by_subject"] if s["subject_id"] == 1)
    assert modelagem["seconds"] == 2700


def test_mock_kind_and_deadline_notion_page(seeded, monkeypatch):
    c = seeded
    mock = c.post("/api/deadlines", json={"subject_id": 5, "title": "Simulado 1 · Seguro", "kind": "mock",
                                          "due_date": "2026-11-19"}).json()
    item = next(i for i in c.get("/api/study/agenda").json() if i["type"] == "deadline" and i["id"] == mock["id"])
    assert item["kind_label"] == "Simulado"

    lab = c.post("/api/deadlines", json={"subject_id": 5, "title": "Laboratório", "kind": "lab",
                                         "due_date": "2026-11-22"}).json()
    # Sem página ligada -> 409 com explicação
    assert c.post("/api/prints/analyze", json={"source": "notion", "deadline_id": lab["id"]}).status_code == 409
    linked = c.put(f"/api/study/deadlines/{lab['id']}/notion", json={"notion_page_id": "lab-page"}).json()
    assert linked["notion_page_id"] == "lab-page"

    monkeypatch.setenv("NOTION_TOKEN", "ntn_teste")
    seen = []

    def notion(req):
        seen.append(str(req.url))
        return httpx.Response(200, json={"results": [
            {"id": "h", "type": "heading_2", "heading_2": {"rich_text": [{"plain_text": "Hash"}]}},
            {"id": "i", "type": "image", "image": {"type": "file", "file": {"url": "https://s3.example/x.png"}}},
        ], "has_more": False})

    app.state.notion_transport = httpx.MockTransport(notion)
    app.state.notion_sleep = lambda s: None
    try:
        secs = c.get("/api/prints/notion-sections", params={"deadline_id": lab["id"]}).json()
    finally:
        del app.state.notion_transport, app.state.notion_sleep
    assert secs == [{"section": "Hash", "images": 1}]
    assert "lab-page" in seen[0]


def test_chat_reads_metrics_only_when_allowed(seeded):
    c = seeded
    # Autorizado em 12/11/2026: ligado por padrão
    assert c.get("/api/settings").json()["values"]["agent_reads_metrics"] is True
    sent = []

    def model(req):
        if req.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "gemma"}]})
        sent.append(json.loads(req.content)["messages"][0]["content"])
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"answer": "ok"}'}}], "usage": {}})

    app.state.llm_transport = httpx.MockTransport(model)
    c.put("/api/settings/default_model", json={"value": "gemma"})
    try:
        c.put("/api/settings/agent_reads_metrics", json={"value": False})
        c.post("/api/agent/chat", json={"message": "Como estou indo?"})
        c.put("/api/settings/agent_reads_metrics", json={"value": True})
        c.post("/api/agent/chat", json={"message": "Como estou indo?"})
    finally:
        del app.state.llm_transport
    assert "não liberado" in sent[0] and "Últimos 30 dias" not in sent[0]
    assert "Últimos 30 dias" in sent[1] and "Engenharia de Requisitos" in sent[1]


def test_migration_turns_simulado_activities_into_mocks(tmp_path, monkeypatch):
    import sqlite3

    db = tmp_path / "m.db"
    monkeypatch.setenv("PAINEL_DB_PATH", str(db))
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    command.upgrade(cfg, "8a3c1d9e4f20")
    con = sqlite3.connect(db)
    con.execute("insert into deadline (title, due_date, kind) values ('Simulado 1 · X', '2026-11-19', 'activity'),"
                " ('Atividade 2', '2026-11-19', 'activity')")
    con.commit()
    con.close()
    command.upgrade(cfg, "head")
    kinds = dict(sqlite3.connect(db).execute("select title, kind from deadline").fetchall())
    assert kinds == {"Simulado 1 · X": "mock", "Atividade 2": "activity"}
    assert date.today()  # sanidade
