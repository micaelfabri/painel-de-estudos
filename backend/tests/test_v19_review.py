"""v1.9: questões da disciplina inteira (D50) e semestres em revisão (D51)."""

import json
from datetime import datetime

import httpx
import pytest

from app import models
from app.main import app
from tests.test_v13_study import FakeModel as _Base
from tests.test_v13_study import _questions


class FakeModel(_Base):
    """O das questões da disciplina também responde com topic_index (como o simulado)."""

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        system = (body.get("messages") or [{}])[0].get("content", "")
        if "disciplina" in system and "topic_index" in system and "simulado" not in system:
            self.requests.append(body)
            content = json.dumps({"summary": "Treino.", "questions": _questions(10, 5, with_topic=True)})
            return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}],
                                             "usage": {"prompt_tokens": 10, "completion_tokens": 5}})
        return super().__call__(request)


@pytest.fixture()
def fake(seeded):
    model = FakeModel()
    app.state.llm_transport = httpx.MockTransport(model)
    seeded.put("/api/settings/default_model", json={"value": "qwen3.5:9b"})
    yield seeded, model
    del app.state.llm_transport


def _seguro(client):
    s = next(x for x in client.get("/api/subjects").json() if x["name"] == "Segurança de Software")
    return s, client.get("/api/topics", params={"subject_id": s["id"]}).json()


def _put_topic(client, t, **kw):
    client.put(f"/api/topics/{t['id']}", json={**{k: v for k, v in t.items() if k != "id"}, **kw})


# --- D50: questões da disciplina ----------------------------------------------------------------


def test_subject_questions_mix_topics_without_timer_and_avoid_repeats(fake):
    client, model = fake
    subject, topics = _seguro(client)
    body = {"subject_id": subject["id"], "n_options": 5}
    assert client.post("/api/agent/question-sets/subject", json=body).status_code == 422  # sem texto salvo
    for t in topics[:2]:
        _put_topic(client, t, source_text=f"Texto do {t['title']}.")

    r = client.post("/api/agent/question-sets/subject", json=body)
    assert r.status_code == 201, r.text
    first = r.json()
    assert first["topic_id"] is None and first["time_limit_minutes"] is None
    assert first["label"] == "questões da disciplina"
    assert first["topic_title"] == f"Questões da disciplina · {subject['name']}"
    assert first["prompt_version"] == "generate_subject_questions.v1"
    sent = model.requests[-1]["messages"][0]["content"]
    assert f"[1] {topics[0]['title']}" in sent and f"[2] {topics[1]['title']}" in sent
    assert "(nenhuma)" in sent  # nada feito ainda

    # Erros vão para o tema de cada questão; nada de reteste agendado
    for q in first["questions"]:
        client.post(f"/api/agent/questions/{q['id']}/answer", json={"chosen_index": 3})
    assert client.get("/api/learning/reviews", params={"include_future": True}).json() == []
    assert {m["topic_id"] for m in client.get("/api/learning/mistakes").json()} <= {topics[0]["id"], topics[1]["id"]}
    hist = client.get("/api/study/history").json()[0]
    assert hist["topic_title"] == "Questões da disciplina" and hist["subject_name"] == subject["name"]

    # A segunda rodada recebe as questões já feitas como lista a evitar
    client.post("/api/agent/question-sets/subject", json=body)
    sent = model.requests[-1]["messages"][0]["content"]
    assert first["questions"][0]["statement"] in sent


# --- D51: semestres em revisão ------------------------------------------------------------------


def _set(s, topic_id, attempt, score):
    qs = models.QuestionSet(topic_id=topic_id, attempt_type=attempt, model="m", prompt_version="p", score=score,
                            completed_at=datetime(2026, 11, 1, 10))
    s.add(qs)


def _review(client, **params):
    return client.get("/api/review", params=params).json()


def _subject(data, name):
    return next(x for g in data["semesters"] for x in g["subjects"] if x["name"] == name)


def test_review_lists_only_finished_subjects_with_reasons(seeded):
    client = seeded
    # Ninguém encerrado ainda: nada em revisão
    assert _review(client)["semesters"] == []
    subject, topics = _seguro(client)
    client.put(f"/api/subjects/{subject['id']}", json={**{k: v for k, v in subject.items() if k != "id"},
                                                       "status": "failed"})
    data = _review(client)
    s = _subject(data, subject["name"])
    assert [r["key"] for r in s["reasons"]] == ["failed"]
    group = data["semesters"][0]
    assert group["code"] and group["counts"]["failed"] == 1


def test_review_reasons_for_a_passed_subject(seeded):
    client = seeded
    subject, topics = _seguro(client)
    client.put(f"/api/subjects/{subject['id']}", json={**{k: v for k, v in subject.items() if k != "id"},
                                                       "status": "passed"})
    with client.session_factory() as s:
        t = {x.id: x for x in s.query(models.Topic).filter(models.Topic.subject_id == subject["id"])}
        ids = [x["id"] for x in topics]
        for tid in ids[:4]:
            t[tid].portal_done = True  # o último tema fica sem concluir no portal
        _set(s, ids[0], "first", 0.9)
        _set(s, ids[0], "retest_7d", 0.9)
        t[ids[0]].learning_status = "learned"
        _set(s, ids[1], "first", 0.8)  # sem o reteste de 7 dias
        t[ids[1]].learning_status = "pending"
        _set(s, ids[2], "first", 0.4)
        _set(s, ids[2], "retest_7d", 0.5)
        t[ids[2]].learning_status = "review"
        qs = models.QuestionSet(topic_id=ids[0], attempt_type="redo", model="m", prompt_version="p")
        s.add(qs)
        s.flush()
        q = models.Question(question_set_id=qs.id, position=1, statement="Q?", options=["a", "b"], correct_index=0)
        s.add(q)
        s.flush()
        s.add(models.Mistake(question_id=q.id, topic_id=ids[0], status="open"))
        s.commit()
    s = _subject(_review(client), subject["name"])
    keys = [r["key"] for r in s["reasons"]]
    assert keys == ["not_learned", "not_consolidated", "not_seen_all"]
    by = {r["key"]: r["detail"] for r in s["reasons"]}
    assert "1 tema(s) em \"rever\"" in by["not_learned"] and "média dos testes 73%" in by["not_learned"]
    assert "1 tema(s) sem o reteste de 7 dias" in by["not_consolidated"]
    assert "1 erro(s) não corrigido(s)" in by["not_consolidated"]
    assert "1 de 5 tema(s) não concluídos no portal" in by["not_seen_all"]
    why = {x["id"]: x["why"] for x in s["topics"]}
    assert why[ids[2]] == ["em \"rever\""] and why[ids[1]] == ["sem o reteste de 7 dias"]
    assert why[ids[4]] == ["não concluído no portal"]


def test_review_nothing_to_review_and_semester_filter(seeded):
    client = seeded
    subject, topics = _seguro(client)
    client.put(f"/api/subjects/{subject['id']}", json={**{k: v for k, v in subject.items() if k != "id"},
                                                       "status": "passed"})
    for t in topics:
        _put_topic(client, t, portal_done=True)
    pp = client.get(f"/api/subjects/{subject['id']}/portal-progress").json()
    client.put(f"/api/subjects/{subject['id']}/portal-progress",
               json={**{k: v for k, v in pp.items() if k not in ("id", "subject_id")}, "contents_done": 5})
    # Aprovada, viu tudo, sem testes nem erros: não entra na revisão
    assert _review(client)["semesters"] == []
    # Filtro por semestre que não tem nada
    assert _review(client, semester_id=999)["semesters"] == []


# --- v1.9.1: disciplina inteira também lê as páginas do Notion -----------------------------------


def test_subject_questions_read_notion_pages_when_no_saved_text(fake, monkeypatch):
    """Tema com texto salvo usa o texto; tema só com página do Notion lê a página na hora (uma vez por página)."""
    from tests.test_f5_integrations import PAGE, FakeNotion

    client, model = fake
    notion = FakeNotion()
    monkeypatch.setenv("NOTION_TOKEN", "ntn_teste")
    app.state.notion_transport = httpx.MockTransport(notion)
    app.state.notion_sleep = lambda s: None
    try:
        subject, topics = _seguro(client)
        _put_topic(client, topics[0], source_text="Texto salvo do primeiro tema.")
        _put_topic(client, topics[1], notion_page_id=PAGE)
        _put_topic(client, topics[2], notion_page_id=PAGE)  # mesma página: vira um bloco só
        r = client.post("/api/agent/question-sets/subject", json={"subject_id": subject["id"], "n_options": 5})
        assert r.status_code == 201, r.text
        sent = model.requests[-1]["messages"][0]["content"]
        assert "Texto salvo do primeiro tema." in sent
        assert f"[2] {topics[1]['title']} / {topics[2]['title']}" in sent and "Valide no servidor." in sent
        assert sum(1 for m in notion.methods if m == "GET") >= 1
        # Nada é gravado no Notion nem no texto dos temas
        assert "PATCH" not in notion.methods
        assert client.get(f"/api/topics/{topics[1]['id']}").json()["source_text"] is None
    finally:
        del app.state.notion_transport
        del app.state.notion_sleep


def test_subject_questions_notion_down_is_clear(fake, monkeypatch):
    client, _ = fake
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    subject, topics = _seguro(client)
    _put_topic(client, topics[0], notion_page_id="11111111-2222-3333-4444-555555555555")
    r = client.post("/api/agent/question-sets/subject", json={"subject_id": subject["id"], "n_options": 5})
    assert r.status_code == 502 and r.json()["detail"]["status"] == "notion_error"
