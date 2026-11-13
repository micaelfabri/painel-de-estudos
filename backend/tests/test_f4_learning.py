"""Testes da F4: retestes 1/7/21, status do tema, prioridade dos retestes, checklist e revisar erros."""

from datetime import date, timedelta

import httpx
import pytest

from app.main import app
from tests.test_f3_agent import TOPIC_TEXT, FakeModel, _topic_id


@pytest.fixture()
def fake(seeded):
    model = FakeModel()
    app.state.llm_transport = httpx.MockTransport(model)
    seeded.put("/api/settings/default_model", json={"value": "qwen3.5:9b"})
    yield seeded, model
    del app.state.llm_transport


def _run_set(client, topic_id, attempt_type, right, text=TOPIC_TEXT):
    """Gera um conjunto e responde `right` questões certas de 10."""
    body = {"topic_id": topic_id, "n_options": 4, "attempt_type": attempt_type}
    if text:
        body["text"] = text
    qs = client.post("/api/agent/question-sets", json=body).json()
    for i, q in enumerate(qs["questions"]):
        client.post(f"/api/agent/questions/{q['id']}/answer", json={"chosen_index": 0 if i < right else 1})
    return qs


def test_first_attempt_schedules_1_7_21(fake):
    client, _ = fake
    topic_id = _topic_id(client)
    _run_set(client, topic_id, "first", 8)
    reviews = client.get("/api/learning/reviews", params={"include_future": True}).json()
    today = date.today()
    assert [(r["attempt_type"], r["due_date"]) for r in reviews] == [
        ("retest_1d", (today + timedelta(days=1)).isoformat()),
        ("retest_7d", (today + timedelta(days=7)).isoformat()),
        ("retest_21d", (today + timedelta(days=21)).isoformat()),
    ]
    # Nada vence hoje
    assert client.get("/api/learning/reviews").json() == []
    assert client.get(f"/api/topics/{topic_id}").json()["learning_status"] == "pending"


def test_7day_retest_decides_learned(fake):
    client, _ = fake
    topic_id = _topic_id(client)
    _run_set(client, topic_id, "first", 6)
    _run_set(client, topic_id, "retest_7d", 7, text=None)  # usa o texto salvo
    assert client.get(f"/api/topics/{topic_id}").json()["learning_status"] == "learned"
    open_7d = [r for r in client.get("/api/learning/reviews", params={"include_future": True}).json()
               if r["attempt_type"] == "retest_7d"]
    assert open_7d == []  # o reteste agendado foi fechado


def test_7day_retest_below_threshold_goes_to_review_and_3d(fake):
    client, _ = fake
    topic_id = _topic_id(client)
    _run_set(client, topic_id, "first", 9)
    _run_set(client, topic_id, "retest_7d", 5, text=None)
    assert client.get(f"/api/topics/{topic_id}").json()["learning_status"] == "review"
    reviews = client.get("/api/learning/reviews", params={"include_future": True}).json()
    three = [r for r in reviews if r["attempt_type"] == "retest_3d"]
    assert len(three) == 1 and three[0]["due_date"] == (date.today() + timedelta(days=3)).isoformat()
    # Passou no reteste de revisão -> aprendido
    _run_set(client, topic_id, "retest_3d", 8, text=None)
    assert client.get(f"/api/topics/{topic_id}").json()["learning_status"] == "learned"


def test_retests_use_new_questions_prompt(fake):
    client, model = fake
    topic_id = _topic_id(client)
    _run_set(client, topic_id, "first", 7)
    _run_set(client, topic_id, "retest_1d", 7, text=None)
    second_prompt = model.requests[-1]["messages"][0]["content"]
    assert "QUESTÕES JÁ FEITAS" in second_prompt and "- Questão 0?" in second_prompt


def test_due_review_comes_first_in_next_action_and_plan(fake):
    client, _ = fake
    topic_id = _topic_id(client)
    _run_set(client, topic_id, "first", 7)
    in_two_days = (date.today() + timedelta(days=2)).isoformat()
    action = client.get("/api/overview", params={"today": in_two_days}).json()["next_action"]
    assert action["kind"] == "review" and "reteste de 1 dia" in action["steps"][0]

    plan = client.post("/api/learning/checklist/plan", params={"day": in_two_days}).json()
    labels = [i["label"] for i in plan["items"]]
    assert labels[0].startswith("Reteste de 1 dia: Tema 4")
    # O estudo da próxima prova entra junto, com a meta do cronômetro
    assert any(label.startswith("Concluir Tema 1 e Tema 2 · Engenharia de Requisitos") for label in labels)
    # Rodar de novo não duplica
    again = client.post("/api/learning/checklist/plan", params={"day": in_two_days}).json()
    assert again["added"] == 0


def test_checklist_e11_toggle(client):
    item = client.post("/api/learning/checklist", json={"day": "2026-11-10", "label": "Tema 4", "planned_minutes": 90}).json()
    done = client.patch(f"/api/learning/checklist/{item['id']}", json={"done": True}).json()
    assert done["done"] is True
    assert client.get("/api/learning/checklist", params={"day": "2026-11-10"}).json()[0]["done"] is True


def test_topic_scores_and_mistakes_review(fake):
    client, _ = fake
    topic_id = _topic_id(client)
    _run_set(client, topic_id, "first", 6)
    scores = client.get("/api/learning/topics").json()
    assert scores[0]["first_score"] == pytest.approx(0.6) and scores[0]["status"] == "pending"
    assert scores[0]["next_review"]["label"] == "reteste de 1 dia"

    mistakes = client.get("/api/learning/mistakes").json()
    assert len(mistakes) == 4 and mistakes[0]["chosen_index"] == 1 and mistakes[0]["correct_index"] == 0
    # v1.5 (D28): "revisado" continua na lista (falta acertar); só some quando for corrigido
    r = client.patch(f"/api/learning/mistakes/{mistakes[0]['id']}", json={"status": "reviewed"})
    assert r.json()["status"] == "reviewed"
    assert len(client.get("/api/learning/mistakes").json()) == 4
    assert len(client.get("/api/learning/mistakes?status=open").json()) == 3
