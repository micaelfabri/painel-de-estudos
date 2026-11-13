"""Testes da v1.5 (SPEC D28–D31): ciclo dos erros, regra do reteste de 21 dias, conversa salva,
gráficos (dia e filtro), nota prevista e simulado em pontos."""

import json
import sqlite3

import httpx
import pytest
from alembic import command
from alembic.config import Config

from app import grading
from app.main import app
from tests.conftest import BACKEND
from tests.test_f3_agent import _topic_id
from tests.test_v13_study import TOPIC_TEXT, _answer_all, _seguro_topics, fake  # noqa: F401


def _statuses(client, **params):
    rows = client.get("/api/learning/mistakes", params={"status": "open,reviewed,again,fixed", **params}).json()
    return sorted(m["status"] for m in rows)


def test_redo_updates_the_original_mistakes(fake):  # noqa: F811
    """Caso real de uso: 9 erros, refez e errou 2 → continuavam 11 abertos. Agora: 9 erros, 7 corrigidos, 2 de novo."""
    client, _ = fake
    _, topics = _seguro_topics(client)
    qs = client.post("/api/agent/question-sets",
                     json={"topic_id": topics[3]["id"], "text": TOPIC_TEXT, "n_options": 5}).json()
    _answer_all(client, qs, right=1)  # 9 erradas
    assert _statuses(client) == ["open"] * 9

    redo = client.post(f"/api/agent/question-sets/{qs['id']}/redo").json()
    # Acerta 7, erra 2: nenhum erro novo, os 9 originais mudam de status
    _answer_all(client, redo, right=7)
    assert _statuses(client) == ["again"] * 2 + ["fixed"] * 7
    assert len(client.get("/api/learning/mistakes").json()) == 2  # padrão: sem os corrigidos

    # Refazer de novo (refazer do refazer): acerta as 2 → tudo corrigido
    redo2 = client.post(f"/api/agent/question-sets/{redo['id']}/redo").json()
    assert len(redo2["questions"]) == 2
    _answer_all(client, redo2, right=2)
    assert _statuses(client) == ["fixed"] * 9

    evo = next(t for t in client.get("/api/study/history/topics").json() if t["topic_id"] == topics[3]["id"])
    assert evo["mistakes"] == {"open": 0, "reviewed": 0, "again": 0, "fixed": 9} and evo["open_mistakes"] == 0


def test_reviewed_then_redo_from_mistakes(fake):  # noqa: F811
    client, model = fake
    sid, topics = _seguro_topics(client)
    qs = client.post("/api/agent/question-sets",
                     json={"topic_id": topics[0]["id"], "text": TOPIC_TEXT, "n_options": 5}).json()
    _answer_all(client, qs, right=7)  # 3 erradas
    first = client.get("/api/learning/mistakes").json()[0]
    assert first["status"] == "open" and first["status_label"] == "não revisado"
    client.patch(f"/api/learning/mistakes/{first['id']}", json={"status": "reviewed"})
    # "corrigido" não é manual
    assert client.patch(f"/api/learning/mistakes/{first['id']}", json={"status": "fixed"}).status_code == 422
    assert _statuses(client) == ["open", "open", "reviewed"]

    calls = len(model.requests)
    redo = client.post("/api/agent/mistakes/redo", json={"subject_id": sid})
    assert redo.status_code == 201, redo.text
    redo = redo.json()
    assert len(redo["questions"]) == 3 and redo["attempt_type"] == "redo" and len(model.requests) == calls
    assert redo["topic_title"] == topics[0]["title"]  # um tema só
    _answer_all(client, redo, right=3)
    assert _statuses(client) == ["fixed"] * 3
    assert client.post("/api/agent/mistakes/redo", json={"subject_id": sid}).status_code == 409

    summary = client.get("/api/learning/mistakes/summary", params={"subject_id": sid}).json()
    assert summary == {"open": 0, "reviewed": 0, "again": 0, "fixed": 3}


def _run_set(client, topic_id, attempt_type, right, text=TOPIC_TEXT):
    body = {"topic_id": topic_id, "n_options": 5, "attempt_type": attempt_type}
    if text:
        body["text"] = text
    qs = client.post("/api/agent/question-sets", json=body).json()
    return _answer_all(client, qs, right)


def test_21day_retest_below_threshold_sends_topic_back(fake):  # noqa: F811
    client, _ = fake
    topic_id = _topic_id(client)
    _run_set(client, topic_id, "first", 6)
    _run_set(client, topic_id, "retest_7d", 8)
    assert client.get(f"/api/topics/{topic_id}").json()["learning_status"] == "learned"
    # 21 dias acima do limiar: continua aprendido
    _run_set(client, topic_id, "retest_21d", 9, text=None)
    assert client.get(f"/api/topics/{topic_id}").json()["learning_status"] == "learned"
    # 21 dias abaixo: volta para revisar, com reteste de 3 dias
    _run_set(client, topic_id, "retest_21d", 5, text=None)
    assert client.get(f"/api/topics/{topic_id}").json()["learning_status"] == "review"
    reviews = client.get("/api/learning/reviews", params={"include_future": True}).json()
    assert any(r["attempt_type"] == "retest_3d" for r in reviews)


def test_chat_is_saved_and_used_as_context(seeded):
    c = seeded
    sent = []

    def model(req):
        if req.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "gemma"}]})
        sent.append(json.loads(req.content)["messages"])
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"answer": "Resposta"}'}}],
                                         "usage": {}})

    app.state.llm_transport = httpx.MockTransport(model)
    c.put("/api/settings/default_model", json={"value": "gemma"})
    try:
        c.post("/api/agent/chat", json={"message": "Primeira pergunta"})
        c.post("/api/agent/chat", json={"message": "Segunda pergunta"})
    finally:
        del app.state.llm_transport
    msgs = c.get("/api/agent/chat/messages").json()
    assert [(m["role"], m["content"]) for m in msgs] == [
        ("user", "Primeira pergunta"), ("assistant", "Resposta"),
        ("user", "Segunda pergunta"), ("assistant", "Resposta")]
    # A segunda chamada levou a primeira troca como contexto (salva no banco, não na tela)
    contents = [m["content"] for m in sent[1]]
    assert "Primeira pergunta" in contents and contents[-1] == "Segunda pergunta"
    assert c.delete("/api/agent/chat/messages").status_code == 204
    assert c.get("/api/agent/chat/messages").json() == []


def test_metrics_subject_filter_and_day_detail(fake):  # noqa: F811
    client, _ = fake
    sid, topics = _seguro_topics(client)
    qs = client.post("/api/agent/question-sets",
                     json={"topic_id": topics[0]["id"], "text": TOPIC_TEXT, "n_options": 5}).json()
    _answer_all(client, qs, right=8)
    client.post("/api/study-sessions", json={"subject_id": sid, "started_at": "2026-11-12T10:00:00", "seconds": 600})
    client.post("/api/study-sessions", json={"subject_id": 1, "started_at": "2026-11-12T11:00:00", "seconds": 300})

    done_day = qs and client.get("/api/study/history").json()[0]["completed_at"][:10]
    m = client.get("/api/study/metrics", params={"today": done_day, "days": 7, "subject_id": sid}).json()
    assert m["subject_id"] == sid and m["scores"][0]["set_id"] == qs["id"]
    assert m["scores"][0]["topic"] == topics[0]["title"]
    other = client.get("/api/study/metrics", params={"today": done_day, "days": 7, "subject_id": 1}).json()
    assert other["scores"] == []

    day = client.get("/api/study/day", params={"day": "2026-11-12"}).json()
    assert day["seconds"] == 900 and len(day["chunks"]) == 2
    only = client.get("/api/study/day", params={"day": "2026-11-12", "subject_id": 1}).json()
    assert only["seconds"] == 300 and only["chunks"][0]["subject_name"] == "Engenharia de Requisitos"
    sets_day = client.get("/api/study/day", params={"day": done_day}).json()
    assert sets_day["sets"][0]["id"] == qs["id"]


def test_predicted_grade_rule_as_data():
    rule = grading.GradingRule.model_validate(grading.PRESETS["padrao_2026"])
    # Dois simulados: 0,8 + sem nota (conta 0 por enquanto); sem AV ainda → quanto falta na AV
    p = grading.predict(rule, [], [0.8, None])
    pa = next(x for x in p["parts"] if x["key"] == "pa")
    assert pa["value"] == pytest.approx(0.8) and pa["pending"] == 1
    assert p["total"] is None and p["needed"] == {"key": "av", "label": "AV/AVS", "value": 5.2, "possible": True}
    # Com AV lançada: total e aprovado
    p = grading.predict(rule, [6.5], [0.8, 0.9])
    assert p["total"] == pytest.approx(8.2) and p["passed"] is True
    # Regra com AP que só soma com AV ≥ 4 (counts_if) e sem fonte de nota: não calcula o que falta
    arq = grading.GradingRule.model_validate(grading.PRESETS["arquitetura_sistemas"])
    p = grading.predict(arq, [], [])
    assert p["needed"] is None and p["parts"][1]["source_label"] == "lançar à mão"


def test_overview_grade_lab_and_mock_points(seeded):
    c = seeded
    sid = next(s["id"] for s in c.get("/api/subjects").json() if s["name"] == "Segurança de Software")
    c.put(f"/api/subjects/{sid}", json={**c.get(f"/api/subjects/{sid}").json(),
                                       "grading_rule": grading.PRESETS["padrao_2026"],
                                       "exam_requires_lab": True})
    mock = c.post("/api/deadlines", json={"subject_id": sid, "title": "Simulado 1", "kind": "mock",
                                          "due_date": "2026-11-19"}).json()
    lab = c.post("/api/deadlines", json={"subject_id": sid, "title": "Lab", "kind": "lab",
                                         "due_date": "2026-11-22"}).json()
    # Simulado: 9 de 10 certas = 0,9 ponto (não 9,0)
    r = c.put(f"/api/study/deadlines/{mock['id']}/result", json={"total_questions": 10, "first_try_correct": 9})
    assert r.json()["score"] == pytest.approx(0.9) and r.json()["max_score"] == 1.0
    assert c.put(f"/api/study/deadlines/{mock['id']}/result", json={"score": 5}).status_code == 422

    subj = next(s for s in c.get("/api/overview").json()["subjects"] if s["id"] == sid)
    assert subj["grade"]["parts"][1]["value"] == pytest.approx(0.9)
    assert subj["grade"]["needed"]["value"] == pytest.approx(5.1)
    assert subj["lab_pending"] is True
    c.patch(f"/api/study/deadlines/{lab['id']}/done", json={"done": True})
    subj = next(s for s in c.get("/api/overview").json()["subjects"] if s["id"] == sid)
    assert subj["lab_pending"] is False

    # A prova segue a regra: AV/AVS vai até 8
    exam = next(i for i in c.get("/api/study/agenda").json() if i["type"] == "exam" and i["subject_id"] == sid)
    assert exam["max_score"] == 8
    assert c.put(f"/api/study/exams/{exam['id']}/result", json={"score": 9}).status_code == 422


def test_migration_merges_redo_copies(tmp_path, monkeypatch):
    """Dados de antes da v1.5: erros criados nas cópias do refazer são juntados ao da questão original."""
    db = tmp_path / "m.db"
    monkeypatch.setenv("PAINEL_DB_PATH", str(db))
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    command.upgrade(cfg, "b4d2e7f1a9c3")
    con = sqlite3.connect(db)

    def insert(table, **values):
        # Preenche as colunas obrigatórias sem padrão com um valor qualquer
        for _, name, typ, notnull, default, pk in con.execute(f"pragma table_info({table})").fetchall():
            if notnull and default is None and not pk and name not in values:
                values[name] = 0 if typ.upper() in ("INTEGER", "BOOLEAN", "FLOAT") else "x"
        cols = ", ".join(values)
        con.execute(f"insert into {table} ({cols}) values ({', '.join('?' * len(values))})", list(values.values()))

    insert("degree", id=1, name="Curso")
    insert("subject", id=1, degree_id=1, name="Disc")
    insert("topic", id=1, subject_id=1, title="Tema")
    for sid, kind, source in ((1, "first", None), (2, "redo", 1), (3, "redo", 2)):
        insert("question_set", id=sid, topic_id=1, attempt_type=kind, source_set_id=source)
    for qid, sid, st in ((1, 1, "A?"), (2, 1, "B?"), (3, 1, "C?"), (11, 2, "A?"), (12, 2, "B?"), (21, 3, "B?")):
        insert("question", id=qid, question_set_id=sid, statement=st, options='["x","y"]', correct_index=0)
    for qid, ok, at in ((1, 0, "10:00"), (2, 0, "10:01"), (3, 1, "10:02"), (11, 1, "11:00"), (12, 0, "11:01"),
                        (21, 1, "12:00")):
        insert("answer", question_id=qid, chosen_index=0 if ok else 1, is_correct=ok, created_at=f"2026-11-12 {at}")
    insert("mistake", id=1, question_id=1, topic_id=1, reviewed=1)
    insert("mistake", id=2, question_id=2, topic_id=1, reviewed=0)
    insert("mistake", id=3, question_id=12, topic_id=1, reviewed=0, video_minute="05:40")
    con.commit()
    con.close()
    command.upgrade(cfg, "head")
    con = sqlite3.connect(db)
    rows = con.execute("select question_id, status, video_minute from mistake order by question_id").fetchall()
    # A: errou, refez certo → fixed. B: errou, errou no refazer (erro da cópia juntado), acertou no 2º → fixed
    assert rows == [(1, "fixed", None), (2, "fixed", "05:40")]
    links = dict(con.execute("select id, source_question_id from question where source_question_id is not null"))
    assert links == {11: 1, 12: 2, 21: 2}


def test_legacy_put_keeps_status_in_sync(fake):  # noqa: F811
    """A rota antiga PUT /api/mistakes só conhece `reviewed`; o status do ciclo acompanha."""
    client, _ = fake
    _, topics = _seguro_topics(client)
    qs = client.post("/api/agent/question-sets",
                     json={"topic_id": topics[0]["id"], "text": TOPIC_TEXT, "n_options": 5}).json()
    _answer_all(client, qs, right=9)
    m = client.get("/api/learning/mistakes").json()[0]
    raw = client.get(f"/api/mistakes/{m['id']}").json()
    client.put(f"/api/mistakes/{m['id']}", json={**raw, "reviewed": True})
    assert client.get("/api/learning/mistakes").json()[0]["status"] == "reviewed"
    client.put(f"/api/mistakes/{m['id']}", json={**raw, "reviewed": False})
    assert client.get("/api/learning/mistakes").json()[0]["status"] == "open"
    # Salvar o minuto do vídeo (a tela manda o registro inteiro) não mexe num erro corrigido
    redo = client.post(f"/api/agent/question-sets/{qs['id']}/redo").json()
    _answer_all(client, redo, right=1)
    raw = client.get(f"/api/mistakes/{m['id']}").json()
    client.put(f"/api/mistakes/{m['id']}", json={**raw, "video_minute": "03:10"})
    row = client.get("/api/learning/mistakes", params={"status": "fixed"}).json()[0]
    assert row["status"] == "fixed" and row["video_minute"] == "03:10"
