"""Testes da v1.6 (SPEC D32–D37): cards dos pontos fracos, dois jeitos de responder, repetição,
prints, transcrições de vídeo, rodada rápida, card do dia e Notion (só acrescenta)."""

import json
from datetime import date, timedelta

import httpx
import pytest

from app.cards import parse_transcript
from app.main import app
from tests.test_v13_study import TOPIC_TEXT, _answer_all, _png, _seguro_topics, materials  # noqa: F401

TODAY = date(2026, 11, 12)


class CardsModel:
    """Modelo falso: questões, cards (citando os erros numerados) e leitura de prints."""

    def __init__(self, prints_queue=None):
        self.requests = []
        self.prints_queue = list(prints_queue or [])

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "gemma"}]})
        body = json.loads(request.content)
        self.requests.append(body)
        system = body["messages"][0]["content"]
        if "cards de revisão" in system:
            n = int(system.split("exatamente ")[1].split(" ")[0])
            video = "TRECHOS DE VÍDEO" in system
            cards = [{"kind": "question", "front": f"Pergunta do erro {i + 1}?", "back": "Resposta.",
                      "explanation": "Porque sim.", "options": ["certa", "b", "c", "d"], "correct_index": 0,
                      "mistake": i + 1, "video_minute": "02:10" if video else None} for i in range(3)]
            # Repete o erro 1 de propósito: não pode virar dois cards do mesmo erro (D32)
            cards.append({**cards[0], "front": "Outra do erro 1?"})
            cards += [{"kind": "concept", "front": f"O que é o conceito {i}?", "back": "Isto.", "explanation": "",
                       "options": ["certa", "b", "c", "d"], "correct_index": 0, "mistake": None,
                       "video_minute": "03:00" if video else None} for i in range(n)]
            content = json.dumps({"cards": cards[:n]})
        elif "UM print" in system:
            content = json.dumps(self.prints_queue.pop(0))
        else:
            content = json.dumps({"summary": "Resumo.", "questions": [
                {"statement": f"Questão {i}?", "options": [f"opção {j}" for j in range(5)], "correct_index": 0,
                 "explanation": "Está no texto."} for i in range(10)]})
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}],
                                         "usage": {"prompt_tokens": 10, "completion_tokens": 5}})


@pytest.fixture()
def model(seeded):
    m = CardsModel()
    app.state.llm_transport = httpx.MockTransport(m)
    seeded.put("/api/settings/default_model", json={"value": "gemma"})
    yield seeded, m
    del app.state.llm_transport


def _with_mistakes(client, right=7):
    sid, topics = _seguro_topics(client)
    qs = client.post("/api/agent/question-sets",
                     json={"topic_id": topics[3]["id"], "text": TOPIC_TEXT, "n_options": 5}).json()
    _answer_all(client, qs, right=right)
    return sid, topics[3]


def test_generate_from_weak_points_and_answer_both_ways(model):
    client, fake = model
    sid, topic = _with_mistakes(client)  # 3 erros "não revisado"
    r = client.post("/api/cards/generate", json={"scope": "weak"}, params={"today": TODAY.isoformat()})
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["topic_id"] == topic["id"] and len(out["cards"]) == 10
    from_mistakes = [c for c in out["cards"] if c["source"] == "mistake"]
    assert len(from_mistakes) == 3 and len({c["mistake_id"] for c in from_mistakes}) == 3  # um card por erro
    first = from_mistakes[0]
    assert first["chosen_text"] and first["mode"] == "answer" and first["due"] is True
    assert first["source_label"] == "Do erro" and first["kind_label"] == "Questão virada card"
    # O prompt levou o texto do tema e os erros numerados com o que eu marquei
    system = fake.requests[-1]["messages"][0]["content"]
    assert "TEXTO DO TEMA" in system and "ele marcou" in system and "Questão 7?" in system

    # Responder errado → erro de origem "revisar de novo", card volta para amanhã
    r = client.post(f"/api/cards/{first['id']}/review", json={"mode": "answer", "chosen_index": 2},
                    params={"today": TODAY.isoformat()}).json()
    assert r["knew"] is False and r["card"]["mistake_status"] == "again"
    assert r["card"]["next_review"] == (TODAY + timedelta(days=1)).isoformat()
    # Responder certo → "corrigido" e próximo passo (1 → 7 dias)
    r = client.post(f"/api/cards/{first['id']}/review", json={"mode": "answer", "chosen_index": 0},
                    params={"today": TODAY.isoformat()}).json()
    assert r["knew"] is True and r["card"]["mistake_status"] == "fixed"
    assert r["card"]["next_review"] == (TODAY + timedelta(days=1)).isoformat()
    r = client.post(f"/api/cards/{first['id']}/review", json={"mode": "answer", "chosen_index": 0},
                    params={"today": TODAY.isoformat()}).json()
    assert r["card"]["next_review"] == (TODAY + timedelta(days=7)).isoformat()

    # Virar: "Sabia" num erro não revisado → "revisado"; "Não sabia" → "revisar de novo"
    second, third = from_mistakes[1], from_mistakes[2]
    r = client.post(f"/api/cards/{second['id']}/review", json={"mode": "flip", "knew": True}).json()
    assert r["card"]["mistake_status"] == "reviewed"
    r = client.post(f"/api/cards/{third['id']}/review", json={"mode": "flip", "knew": False}).json()
    assert r["card"]["mistake_status"] == "again"
    assert client.post(f"/api/cards/{third['id']}/review", json={"mode": "flip"}).status_code == 422

    # Gerar de novo não repete erro que já virou card
    again = client.post("/api/cards/generate", json={"scope": "topic", "topic_id": topic["id"]},
                        params={"today": TODAY.isoformat()}).json()
    assert all(c["source"] != "mistake" for c in again["cards"])


def test_three_right_answers_move_card_to_flip(model):
    client, _ = model
    _with_mistakes(client)
    card = client.post("/api/cards/generate", json={}, params={"today": TODAY.isoformat()}).json()["cards"][0]
    for i in range(3):
        r = client.post(f"/api/cards/{card['id']}/review", json={"mode": "answer", "chosen_index": 0},
                        params={"today": (TODAY + timedelta(days=30 * i)).isoformat()}).json()
    assert r["card"]["mode"] == "flip"  # D33: lembrar é mais difícil


def test_summary_round_day_card_and_plan(model):
    client, _ = model
    sid, topic = _with_mistakes(client)
    cards = client.post("/api/cards/generate", json={}, params={"today": TODAY.isoformat()}).json()["cards"]
    s = client.get("/api/cards/summary", params={"today": TODAY.isoformat()}).json()
    assert s["total"] == 10 and s["due"] == 10 and s["topics"][0]["topic_id"] == topic["id"]

    rnd = client.post("/api/cards/round", json={"size": 10}, params={"today": TODAY.isoformat()}).json()
    assert len(rnd) == 10 and rnd[0]["source"] == "mistake"  # erros primeiro

    day = client.get("/api/cards/today", params={"today": TODAY.isoformat()}).json()
    assert day["card"] and day["answered"] is False
    # O card do dia fica o mesmo o dia todo
    assert client.get("/api/cards/today", params={"today": TODAY.isoformat()}).json()["card"]["id"] == day["card"]["id"]

    plan = client.post("/api/learning/checklist/plan", params={"day": TODAY.isoformat()}).json()
    assert any(i["label"] == "Revisar cards vencidos (10)" for i in plan["items"])
    plan = client.post("/api/learning/checklist/plan", params={"day": TODAY.isoformat()}).json()
    assert sum(i["label"].startswith("Revisar cards") for i in plan["items"]) == 1  # não duplica

    # Histórico e Desempenho
    client.post(f"/api/cards/{cards[0]['id']}/review", json={"mode": "flip", "knew": True})
    evo = next(t for t in client.get("/api/study/history/topics").json() if t["topic_id"] == topic["id"])
    assert evo["cards"] == 10
    m = client.get("/api/study/metrics", params={"days": 7}).json()
    assert m["totals"]["cards_reviewed"] == 1 and sum(d["cards"] for d in m["daily"]) == 1
    assert client.get("/api/overview").json()["cards_due"] >= 9


def test_nothing_to_generate(model):
    client, _ = model
    r = client.post("/api/cards/generate", json={})
    assert r.status_code == 409
    assert client.post("/api/cards/round", json={}).status_code == 409
    assert client.get("/api/cards/today").json() == {"card": None, "answered": False}


def test_cards_from_prints(model, materials):  # noqa: F811
    client, fake = model
    _, topics = _seguro_topics(client)
    fake.prints_queue = [
        {"result": "wrong", "statement": "O que é XSS?", "options": ["Injeção de script", "Banco", "Rede", "Disco"],
         "correct_index": 0, "chosen_index": 2, "explanation": "Script no navegador."},
        {"result": "correct", "statement": "Fácil?", "options": ["sim", "não"], "correct_index": 0,
         "chosen_index": 0, "explanation": ""},
        {"result": "wrong", "statement": "", "options": [], "correct_index": None, "chosen_index": None,
         "explanation": ""},
    ]
    r = client.post("/api/cards/from-prints", json={"topic_id": topics[0]["id"], "source": "folder",
                                                    "paths": ["Segurança de Software/Lab"]})
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["images"] == 3 and len(out["cards"]) == 1
    card = out["cards"][0]
    assert card["front"] == "O que é XSS?" and card["back"] == "Injeção de script" and card["chosen_text"] == "Rede"
    assert card["source"] == "print" and card["source_detail"]
    assert [s["reason"] for s in out["skipped"]] == ["acertou (não vira card)", "não deu para ler a questão inteira"]
    # A imagem foi para o modelo local como data URL, com o prompt de transcrição
    msg = fake.requests[0]["messages"]
    assert "Transcreva" in msg[0]["content"] and msg[1]["content"][1]["image_url"]["url"].startswith("data:image")


def test_transcript_parsing_and_cards_from_video(model, materials):  # noqa: F811
    client, fake = model
    vtt = "WEBVTT\n\n1\n00:02:10.000 --> 00:02:14.000\nInjeção de SQL acontece\n\n2\n00:02:14.000 --> 00:02:18.000\n<i>quando o dado vira código</i>\n"
    assert parse_transcript(vtt, ".vtt") == "[02:10] Injeção de SQL acontece\n[02:14] quando o dado vira código"
    srt = "1\n01:00:05,000 --> 01:00:07,000\nUma hora depois\n"
    assert parse_transcript(srt, ".srt") == "[60:05] Uma hora depois"
    (materials / "Segurança de Software" / "aula4.vtt").write_text(vtt, encoding="utf-8")
    listed = client.get("/api/prints/folder", params={"path": "Segurança de Software", "kind": "transcripts"}).json()
    assert [e["name"] for e in listed["entries"]] == ["Lab", "aula4.vtt", "notas.txt"]

    _, topics = _seguro_topics(client)
    r = client.post("/api/cards/from-transcript", json={"topic_id": topics[0]["id"],
                                                        "path": "Segurança de Software/aula4.vtt", "n": 5})
    assert r.status_code == 201, r.text
    cards = r.json()["cards"]
    assert cards and all(c["source"] == "video" and c["video_minute"] in ("02:10", "03:00") for c in cards)
    assert all(c["kind"] != "question" for c in cards)  # sem erro de origem, "question" vira "concept"
    assert cards[0]["source_detail"] == "aula4.vtt"
    assert "[02:10] Injeção de SQL" in fake.requests[-1]["messages"][0]["content"]
    for bad in ("../segredo.png", "Segurança de Software/Lab"):
        assert client.post("/api/cards/from-transcript",
                           json={"topic_id": topics[0]["id"], "path": bad}).status_code in (400, 404)


def test_notion_export_only_appends(model, monkeypatch):
    client, _ = model
    monkeypatch.setenv("NOTION_TOKEN", "ntn_teste")
    _, topic = _with_mistakes(client)
    topic["notion_page_id"] = "page-1"
    client.put(f"/api/topics/{topic['id']}", json={k: v for k, v in topic.items() if k != "id"})
    client.post("/api/cards/generate", json={"scope": "topic", "topic_id": topic["id"]})
    calls = []

    def notion_api(req):
        calls.append((req.method, req.url.path, json.loads(req.content) if req.content else None))
        return httpx.Response(200, json={"results": []})

    app.state.notion_transport = httpx.MockTransport(notion_api)
    app.state.notion_sleep = lambda s: None
    try:
        r = client.post(f"/api/cards/topics/{topic['id']}/notion")
        again = client.post(f"/api/cards/topics/{topic['id']}/notion")
    finally:
        del app.state.notion_transport, app.state.notion_sleep
    assert r.json() == {"sent": 10} and again.json() == {"sent": 0}  # não manda de novo
    assert [m for m, _, _ in calls] == ["PATCH"]  # só acrescenta blocos; nunca DELETE
    blocks = calls[0][2]["children"]
    assert blocks[0]["type"] == "heading_3" and blocks[1]["type"] == "toggle"


def test_usage_log_is_paginated(seeded):
    """v1.7: registro de uso 10 por página, mais recente primeiro."""
    from app import db as db_module
    from app import models

    session = next(app.dependency_overrides[db_module.get_session]())
    for i in range(23):
        session.add(models.LlmCall(model="m", prompt_name="chat", prompt_version="v3", latency_ms=i, attempts=1,
                                   status="ok"))
    session.commit()
    session.close()
    first = seeded.get("/api/agent/usage").json()
    assert first["total"] == 23 and first["pages"] == 3 and len(first["items"]) == 10
    assert first["items"][0]["latency_ms"] == 22  # mais recente primeiro
    last = seeded.get("/api/agent/usage", params={"page": 3}).json()
    assert len(last["items"]) == 3 and last["page"] == 3
    assert seeded.get("/api/agent/usage", params={"page": 99}).json()["page"] == 3


def test_timestamps_are_local_time(seeded, monkeypatch):
    """v1.7: created_at sai em hora local (TZ), não no UTC do CURRENT_TIMESTAMP do SQLite."""
    import time
    from datetime import datetime

    from app import db as db_module
    from app import models

    monkeypatch.setenv("TZ", "America/Sao_Paulo")
    time.tzset()
    try:
        session = next(app.dependency_overrides[db_module.get_session]())
        row = models.LlmCall(model="m", prompt_name="chat", prompt_version="v3", latency_ms=1, attempts=1, status="ok")
        session.add(row)
        session.commit()
        session.refresh(row)
        assert abs((row.created_at - datetime.now()).total_seconds()) < 60
        session.close()
    finally:
        monkeypatch.delenv("TZ")
        time.tzset()
