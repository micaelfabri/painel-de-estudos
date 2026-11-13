"""Testes da F5: Notion (ler texto, gravar resultado no fim) e Google Agenda (agenda própria, nunca apagar)."""

import json
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.main import app
from tests.test_f3_agent import TOPIC_TEXT, FakeModel, _topic_id

PAGE = "11111111-2222-3333-4444-555555555555"


def _rt(text):
    return {"rich_text": [{"plain_text": text}]}


class FakeNotion:
    def __init__(self, fail_append=False):
        self.appended = []
        self.methods = []
        self.sleeps = []
        self.fail_append = fail_append
        self.throttle_next = 0  # quantos 429 devolver antes de responder
        self.search_pages = 1

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.methods.append(request.method)
        assert request.headers["Authorization"] == "Bearer ntn_teste"
        path = request.url.path
        if self.throttle_next:
            self.throttle_next -= 1
            return httpx.Response(429, headers={"Retry-After": "2"}, json={"message": "rate limited"})
        if path.endswith("/search"):
            body = json.loads(request.content)
            n = int(body.get("start_cursor", "0"))
            page = {"object": "page", "id": PAGE if n == 0 else f"p{n}", "url": "https://notion.so/x",
                    "last_edited_time": "2026-11-10",
                    "properties": {"title": {"type": "title", "title": [{"plain_text": "Tema 4 · Seguro" if n == 0 else f"P{n}"}]}}}
            more = n + 1 < self.search_pages
            return httpx.Response(200, json={"results": [page], "has_more": more, "next_cursor": str(n + 1) if more else None})
        if path.endswith(f"/blocks/{PAGE}/children") and request.method == "GET":
            return httpx.Response(200, json={"has_more": False, "results": [
                {"id": "b1", "type": "heading_2", "heading_2": _rt("Validação de entrada"), "has_children": False},
                {"id": "b2", "type": "paragraph", "paragraph": _rt("Valide no servidor."), "has_children": False},
                {"id": "b3", "type": "toggle", "toggle": _rt("Exemplos"), "has_children": True},
                {"id": "b4", "type": "image", "image": {}, "has_children": False},
            ]})
        if path.endswith("/blocks/b3/children"):
            return httpx.Response(200, json={"has_more": False, "results": [
                {"id": "b5", "type": "bulleted_list_item", "bulleted_list_item": _rt("SQL injection"), "has_children": False}]})
        if path.endswith(f"/blocks/{PAGE}/children") and request.method == "PATCH":
            if self.fail_append:
                return httpx.Response(503, json={"message": "fora do ar"})
            self.appended.append(json.loads(request.content)["children"])
            return httpx.Response(200, json={"results": []})
        return httpx.Response(404, json={"message": "não achei"})


@pytest.fixture()
def notion(seeded, monkeypatch):
    monkeypatch.setenv("NOTION_TOKEN", "ntn_teste")
    fake = FakeNotion()
    app.state.notion_transport = httpx.MockTransport(fake)
    app.state.notion_sleep = fake.sleeps.append  # sem esperar de verdade nos testes
    app.state.llm_transport = httpx.MockTransport(FakeModel())
    seeded.put("/api/settings/default_model", json={"value": "qwen3.5:9b"})
    topic_id = _topic_id(seeded)
    t = seeded.get(f"/api/topics/{topic_id}").json()
    t["notion_page_id"] = PAGE
    seeded.put(f"/api/topics/{topic_id}", json=t)
    yield seeded, fake, topic_id
    del app.state.notion_transport
    del app.state.notion_sleep
    del app.state.llm_transport


def _answer_all(client, topic_id, right=7):
    qs = client.post("/api/agent/question-sets", json={"topic_id": topic_id, "text": TOPIC_TEXT, "n_options": 4}).json()
    last = None
    for i, q in enumerate(qs["questions"]):
        last = client.post(f"/api/agent/questions/{q['id']}/answer", json={"chosen_index": 0 if i < right else 1}).json()
    return last


def test_notion_status_and_pages(notion):
    client, _, _ = notion
    st = client.get("/api/notion/status").json()
    assert st["configured"] and st["reachable"] and st["pages"] == 1
    assert client.get("/api/notion/pages").json()[0]["title"] == "Tema 4 · Seguro"


def test_notion_topic_text_only_text_with_children(notion):
    client, _, topic_id = notion
    out = client.get(f"/api/notion/topics/{topic_id}/text").json()
    assert out["text"] == "## Validação de entrada\nValide no servidor.\nExemplos\n  - SQL injection"


def test_result_appended_at_end_never_deleted(notion):
    client, fake, topic_id = notion
    last = _answer_all(client, topic_id, right=7)
    assert last["notion_sync"] == "ok"
    blocks = fake.appended[0]
    assert blocks[0]["type"] == "heading_3" and "primeira vez" in blocks[0]["heading_3"]["rich_text"][0]["text"]["content"]
    assert "70% (7 de 10)" in blocks[1]["paragraph"]["rich_text"][0]["text"]["content"]
    assert sum(1 for b in blocks if b["type"] == "bulleted_list_item") == 3  # as 3 erradas
    assert "DELETE" not in fake.methods
    # Não grava de novo
    assert client.post("/api/notion/sync").json()["ok"] == 0


def test_failed_append_stays_pending_and_sync_retries(notion):
    client, fake, topic_id = notion
    fake.fail_append = True
    last = _answer_all(client, topic_id)
    assert last["notion_sync"].startswith("Erro do Notion (503)")
    assert client.get("/api/notion/status").json()["pending_results"] == 1
    fake.fail_append = False
    assert client.post("/api/notion/sync").json()["ok"] == 1
    assert client.get("/api/notion/status").json()["pending_results"] == 0


def test_notion_429_waits_and_retries(notion):
    client, fake, topic_id = notion
    fake.throttle_next = 2
    out = client.get(f"/api/notion/topics/{topic_id}/text")
    assert out.status_code == 200
    assert fake.sleeps.count(2.0) == 2  # respeitou o Retry-After nas duas vezes


def test_notion_429_gives_up_with_clear_message(notion):
    client, fake, topic_id = notion
    fake.throttle_next = 99
    r = client.get(f"/api/notion/topics/{topic_id}/text")
    assert r.status_code == 502 and "429" in r.json()["detail"]


def test_notion_pages_are_paginated(notion):
    client, fake, _ = notion
    fake.search_pages = 3
    assert [p["title"] for p in client.get("/api/notion/pages").json()] == ["Tema 4 · Seguro", "P1", "P2"]


def test_notion_text_is_split_by_top_headings(notion):
    client, _, topic_id = notion
    out = client.get(f"/api/notion/topics/{topic_id}/text").json()
    assert [s["title"] for s in out["sections"]] == ["Validação de entrada"]
    assert out["sections"][0]["text"].endswith("SQL injection")


def test_notion_without_token_is_clear(seeded, monkeypatch):
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    assert seeded.get("/api/notion/status").json()["configured"] is False
    r = seeded.get("/api/notion/pages")
    assert r.status_code == 409 and "NOTION_TOKEN" in r.json()["detail"]


# --- Google Agenda -----------------------------------------------------------


class FakeGoogle:
    def __init__(self):
        self.calls = []
        self.events = {}  # id -> evento
        self.calendars = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, request.url.path))
        path = request.url.path
        if request.url.host == "oauth2.googleapis.com":
            form = parse_qs(request.content.decode())
            if form["grant_type"] == ["authorization_code"]:
                assert form["code_verifier"][0] and form["redirect_uri"] == ["http://localhost:8000/api/google/callback"]
                return httpx.Response(200, json={"access_token": "at1", "refresh_token": "rt1", "expires_in": 3600})
            return httpx.Response(200, json={"access_token": "at2", "expires_in": 3600})
        if request.method == "POST" and path == "/calendar/v3/calendars":
            self.calendars["cal1"] = json.loads(request.content)
            return httpx.Response(200, json={"id": "cal1"})
        if request.method == "GET" and path == "/calendar/v3/calendars/cal1":
            return httpx.Response(200, json={"id": "cal1"})
        if path.startswith("/calendar/v3/calendars/cal1/events"):
            parts = path.split("/")
            if request.method == "POST":
                ev = json.loads(request.content)
                ev["id"] = f"ev{len(self.events) + 1}"
                self.events[ev["id"]] = ev
                return httpx.Response(200, json=ev)
            ev_id = parts[-1]
            if ev_id not in self.events:
                return httpx.Response(404, json={"error": {"message": "Not Found"}})
            if request.method == "GET":
                return httpx.Response(200, json=self.events[ev_id])
            if request.method == "PATCH":
                self.events[ev_id].update(json.loads(request.content))
                return httpx.Response(200, json=self.events[ev_id])
        if request.method == "GET" and path == "/calendar/v3/calendars/primary/events":
            return httpx.Response(200, json={"items": [
                {"summary": "Bloco de estudo", "start": {"dateTime": "2026-11-12T19:00:00-03:00"}},
                {"summary": "Prova · X", "start": {"dateTime": "2026-11-17T17:00:00-03:00"},
                 "extendedProperties": {"private": {"painel": "1"}}},
                {"summary": "Feriado", "start": {"date": "2026-11-15"}},
            ]})
        return httpx.Response(404, json={"error": {"message": "?"}})


@pytest.fixture()
def google(seeded, tmp_path, monkeypatch):
    monkeypatch.setenv("PAINEL_SECRETS_DIR", str(tmp_path))
    (tmp_path / "google_client.json").write_text(json.dumps(
        {"installed": {"client_id": "cid.apps.googleusercontent.com", "client_secret": "csecret"}}))
    fake = FakeGoogle()
    app.state.google_transport = httpx.MockTransport(fake)
    yield seeded, fake, tmp_path
    del app.state.google_transport


def _login(client):
    r = client.get("/api/google/login", headers={"Host": "localhost:8000"}, follow_redirects=False)
    assert r.status_code == 302
    q = parse_qs(urlparse(r.headers["location"]).query)
    assert q["scope"] == ["https://www.googleapis.com/auth/calendar.app.created "
                          "https://www.googleapis.com/auth/calendar.events.readonly"]
    assert q["code_challenge_method"] == ["S256"] and q["access_type"] == ["offline"]
    cb = client.get("/api/google/callback", params={"code": "c1", "state": q["state"][0]},
                    headers={"Host": "localhost:8000"}, follow_redirects=False)
    assert cb.headers["location"] == "/gerenciar/configuracoes?google=ok"


def test_google_login_saves_token(google):
    client, _, secrets = google
    assert client.get("/api/google/status").json() == {"client_file": True, "connected": False,
                                                       "calendar_id": None, "calendar_name": "Painel de Estudos"}
    _login(client)
    tok = json.loads((secrets / "google_token.json").read_text())
    assert tok["refresh_token"] == "rt1"
    # state reaproveitado não vale
    bad = client.get("/api/google/callback", params={"code": "c1", "state": "outro"}, follow_redirects=False)
    assert bad.headers["location"].endswith("google=erro")


def test_sync_exams_creates_own_calendar_then_updates(google):
    client, fake, _ = google
    _login(client)
    first = client.post("/api/google/sync-exams").json()
    assert first["created"] >= 1 and first["updated"] == 0
    assert client.get("/api/google/status").json()["calendar_id"] == "cal1"
    ev = next(iter(fake.events.values()))
    assert ev["extendedProperties"]["private"]["painel"] == "1" and ev["summary"].startswith("Prova · ")
    second = client.post("/api/google/sync-exams").json()
    assert second == {"created": 0, "updated": first["created"]}
    assert not any(m == "DELETE" for m, _ in fake.calls)
    # Só escreve na agenda do painel, nunca na principal
    assert not any(m in ("POST", "PATCH", "PUT") and "/primary" in p for m, p in fake.calls)


def test_event_not_marked_by_panel_is_never_edited(google):
    client, fake, _ = google
    _login(client)
    client.post("/api/google/sync-exams")
    ev_id = next(iter(fake.events))
    fake.events[ev_id]["extendedProperties"] = {"private": {}}  # alguém mexeu: não é mais do painel
    client.post("/api/google/sync-exams")
    assert not any(m == "PATCH" and p.endswith(ev_id) for m, p in fake.calls)


def test_expired_token_is_refreshed(google):
    client, _, secrets = google
    _login(client)
    tok = json.loads((secrets / "google_token.json").read_text())
    tok["expires_at"] = time.time() - 10
    (secrets / "google_token.json").write_text(json.dumps(tok))
    client.post("/api/google/sync-exams")
    tok = json.loads((secrets / "google_token.json").read_text())
    assert tok["access_token"] == "at2" and tok["refresh_token"] == "rt1"


def test_primary_events_read_only_and_panel_events_hidden(google):
    client, _, _ = google
    assert client.get("/api/google/events").json() == {"connected": False, "events": []}
    _login(client)
    out = client.get("/api/google/events", params={"start": "2026-11-10"}).json()
    assert [e["title"] for e in out["events"]] == ["Bloco de estudo", "Feriado"]
    assert out["events"][0]["time"] == "19:00" and out["events"][1]["time"] is None


def test_missing_client_file_is_clear(google):
    client, _, secrets = google
    (secrets / "google_client.json").unlink()
    r = client.get("/api/google/login", follow_redirects=False)
    assert r.status_code == 409 and "google_client.json" in r.json()["detail"]


def test_sync_only_the_exams_confirmed(google):
    """v1.5: a tela lista as provas e manda só as marcadas (eu já crio as minhas na agenda)."""
    client, fake, _ = google
    _login(client)
    preview = client.get("/api/google/sync-exams/preview").json()
    assert preview and all(not p["sent"] for p in preview)
    assert client.post("/api/google/sync-exams", json={"exam_ids": []}).json() == {"created": 0, "updated": 0}
    assert fake.events == {}
    out = client.post("/api/google/sync-exams", json={"exam_ids": [preview[0]["id"]]}).json()
    assert out == {"created": 1, "updated": 0} and len(fake.events) == 1
    assert client.get("/api/google/sync-exams/preview").json()[0]["sent"] is True
