"""Testes da v1.3 (SPEC D13–D21): histórico, refazer erradas, testes de foco, simulado,
provas e prazos no lado Estudo, resumo da semana, backup e notas pelos prints."""

import io
import json
from datetime import date

import httpx
import pytest
from PIL import Image

from app import study
from app.integrations import prints
from app.main import app

TOPIC_TEXT = "Autenticação verifica a identidade do usuário. Autorização define o que ele pode acessar."


def _questions(n, n_options, with_topic=False):
    out = []
    for i in range(n):
        q = {"statement": f"Questão {i}?", "options": [f"opção {j}" for j in range(n_options)],
             "correct_index": 0, "explanation": "Está no texto."}
        if with_topic:
            q["topic_index"] = 1 + i % 2
        out.append(q)
    return out


class FakeModel:
    """Responde conforme o prompt; guarda os pedidos e uma fila de leituras de prints."""

    def __init__(self, prints_queue=None, vision_number=7):
        self.requests = []
        self.prints_queue = list(prints_queue or [])
        self.vision_number = vision_number

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "gemma"}]})
        body = json.loads(request.content)
        self.requests.append(body)
        system = body["messages"][0]["content"]
        if "UM print" in system:
            content = json.dumps(self.prints_queue.pop(0))
        elif "simulado" in system:
            content = json.dumps({"summary": "Simulado.", "questions": _questions(10, 5, with_topic=True)})
        elif "múltipla escolha" in system:
            content = json.dumps({"summary": "Resumo.", "questions": _questions(10, 5)})
        else:
            content = json.dumps({"number": self.vision_number})
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}],
                                         "usage": {"prompt_tokens": 10, "completion_tokens": 5}})


@pytest.fixture()
def fake(seeded):
    model = FakeModel()
    app.state.llm_transport = httpx.MockTransport(model)
    seeded.put("/api/settings/default_model", json={"value": "gemma"})
    yield seeded, model
    del app.state.llm_transport


def _seguro_topics(client):
    seguro = next(s for s in client.get("/api/subjects").json() if s["name"] == "Segurança de Software")
    return seguro["id"], client.get("/api/topics", params={"subject_id": seguro["id"]}).json()


def _answer_all(client, qs, right):
    res = None
    for i, q in enumerate(qs["questions"]):
        res = client.post(f"/api/agent/questions/{q['id']}/answer", json={"chosen_index": 0 if i < right else 1}).json()
    return res


def test_history_keeps_every_set_and_redo_wrong(fake):
    client, model = fake
    _, topics = _seguro_topics(client)
    qs = client.post("/api/agent/question-sets",
                     json={"topic_id": topics[3]["id"], "text": TOPIC_TEXT, "n_options": 5}).json()
    _answer_all(client, qs, right=5)

    # O conjunto continua salvo e aparece no histórico (o reteste de 50% não se perde no F5)
    hist = client.get("/api/study/history").json()
    assert hist[0]["id"] == qs["id"] and hist[0]["score"] == pytest.approx(0.5)
    assert hist[0]["right"] == 5 and hist[0]["wrong"] == 5 and hist[0]["label"] == "primeira vez"

    # Refazer erradas: só as 5 erradas, sem chamar o modelo
    calls = len(model.requests)
    redo = client.post(f"/api/agent/question-sets/{qs['id']}/redo")
    assert redo.status_code == 201, redo.text
    redo = redo.json()
    assert len(redo["questions"]) == 5 and redo["label"] == "refazer erradas"
    assert [q["statement"] for q in redo["questions"]] == [f"Questão {i}?" for i in range(5, 10)]
    assert len(model.requests) == calls
    _answer_all(client, redo, right=5)

    # Refazer não mexe no ciclo de retestes do tema
    reviews = client.get("/api/learning/reviews", params={"include_future": True}).json()
    assert len([r for r in reviews if r["topic_id"] == topics[3]["id"]]) == 3

    # Sem erradas -> 409
    assert client.post(f"/api/agent/question-sets/{redo['id']}/redo").status_code == 409

    # Evolução por tema: as duas notas, em ordem
    evo = next(t for t in client.get("/api/study/history/topics").json() if t["topic_id"] == topics[3]["id"])
    assert [p["score"] for p in evo["points"]] == [pytest.approx(0.5), pytest.approx(1.0)]


def test_focus_tests_use_my_errors_or_hits(fake):
    client, model = fake
    _, topics = _seguro_topics(client)
    tid = topics[3]["id"]
    # Sem histórico ainda -> 409 com explicação
    assert client.post("/api/agent/question-sets/focus",
                       json={"topic_id": tid, "focus": "errors", "n_options": 5}).status_code == 422  # sem texto
    qs = client.post("/api/agent/question-sets", json={"topic_id": tid, "text": TOPIC_TEXT, "n_options": 5}).json()
    _answer_all(client, qs, right=8)

    r = client.post("/api/agent/question-sets/focus", json={"topic_id": tid, "focus": "errors", "n_options": 5})
    assert r.status_code == 201, r.text
    assert r.json()["label"] == "novo teste (erros)" and r.json()["prompt_version"] == "generate_focused.v1"
    sent = model.requests[-1]["messages"][0]["content"]
    assert "ERROU" in sent and "Questão 8?" in sent and "Questão 0?" not in sent

    r = client.post("/api/agent/question-sets/focus", json={"topic_id": tid, "focus": "hits", "n_options": 5})
    assert r.status_code == 201
    sent = model.requests[-1]["messages"][0]["content"]
    assert "ACERTOU" in sent and "Questão 0?" in sent


def test_simulation_mixes_topics_and_finishes_on_timeout(fake):
    client, model = fake
    subject_id, topics = _seguro_topics(client)
    # Sem nenhum texto salvo -> 422
    assert client.post("/api/agent/simulations", json={"subject_id": subject_id, "n_options": 5}).status_code == 422
    for t in topics[:2]:
        t["source_text"] = f"Texto do {t['title']}."
        client.put(f"/api/topics/{t['id']}", json={k: v for k, v in t.items() if k != "id"})

    r = client.post("/api/agent/simulations", json={"subject_id": subject_id, "n_options": 5})
    assert r.status_code == 201, r.text
    sim = r.json()
    assert sim["topic_id"] is None and sim["time_limit_minutes"] == 60 and sim["label"] == "simulado da prova"
    sent = model.requests[-1]["messages"][0]["content"]
    assert f"[1] {topics[0]['title']}" in sent and f"[2] {topics[1]['title']}" in sent

    # Respondo 3 e o tempo acaba: as 7 restantes contam como erradas, com o erro no tema certo
    for q in sim["questions"][:3]:
        client.post(f"/api/agent/questions/{q['id']}/answer", json={"chosen_index": 0})
    done = client.post(f"/api/agent/question-sets/{sim['id']}/finish").json()
    assert done["score"] == pytest.approx(0.3) and done["completed_at"]
    mistakes = client.get("/api/learning/mistakes").json()
    assert len(mistakes) == 7 and {m["topic_id"] for m in mistakes} == {topics[0]["id"], topics[1]["id"]}
    # O simulado não cria retestes nem vai para o Notion
    assert client.get("/api/learning/reviews", params={"include_future": True}).json() == []
    assert client.get("/api/study/history").json()[0]["topic_title"] == "Simulado"


def test_agenda_done_and_results(seeded):
    client = seeded
    items = client.get("/api/study/agenda").json()
    exam = next(i for i in items if i["type"] == "exam")
    assert client.patch(f"/api/study/exams/{exam['id']}/done", json={"done": True}).json()["done"] is True

    subject_id, _ = _seguro_topics(client)
    lab = client.post("/api/deadlines", json={"subject_id": subject_id, "title": "Laboratório", "kind": "lab",
                                              "due_date": "2026-11-22"}).json()
    r = client.put(f"/api/study/deadlines/{lab['id']}/result",
                   json={"total_questions": 10, "first_try_correct": 7, "wrong_attempts": 4})
    assert r.status_code == 200, r.text
    assert r.json()["score"] == 7.0 and r.json()["done"] is True and r.json()["kind_label"] == "Laboratório"
    assert client.put(f"/api/study/deadlines/{lab['id']}/result",
                      json={"total_questions": 5, "first_try_correct": 7}).status_code == 422
    # Desmarcar
    assert client.patch(f"/api/study/deadlines/{lab['id']}/done", json={"done": False}).json()["done"] is False

    # Concluídos aparecem marcados na faixa de 14 dias
    over = client.get("/api/overview", params={"today": "2026-11-12"}).json()
    flat = [i for d in over["timeline"] for i in d["items"]]
    assert any(i["category"] == "exam" and i["done"] for i in flat)

    # O cadastro também calcula a nota quando vêm os acertos
    d = client.post("/api/deadlines", json={"title": "Atividade", "kind": "activity", "due_date": "2026-11-20",
                                            "total_questions": 4, "first_try_correct": 3}).json()
    assert d["score"] == 7.5


def test_week_summary(fake):
    client, _ = fake
    _, topics = _seguro_topics(client)
    client.post("/api/study-sessions", json={"started_at": f"{date.today()}T10:00:00",
                                             "ended_at": f"{date.today()}T11:00:00", "seconds": 3600})
    qs = client.post("/api/agent/question-sets",
                     json={"topic_id": topics[3]["id"], "text": TOPIC_TEXT, "n_options": 5}).json()
    _answer_all(client, qs, right=6)
    week = client.get("/api/study/week").json()
    assert week["seconds"] == 3600 and week["sets"] == 1 and week["average_score"] == pytest.approx(0.6)


def test_daily_backup_keeps_14(tmp_path):
    import sqlite3

    db = tmp_path / "painel.db"
    sqlite3.connect(db).execute("create table t (x)").connection.commit()
    for day in range(1, 20):
        study.daily_backup(db, date(2026, 11, day))
    files = sorted((tmp_path / "backups").glob("painel-*.db"))
    assert len(files) == 14 and files[-1].name == "painel-2026-11-19.db" and files[0].name == "painel-2026-11-06.db"
    # Mesmo dia de novo: não duplica
    study.daily_backup(db, date(2026, 11, 19))
    assert len(list((tmp_path / "backups").glob("painel-*.db"))) == 14


def test_footer_links_settings(seeded):
    s = seeded.get("/api/settings").json()["values"]
    # Cópia pública: sem links de exemplo; cada um preenche os seus em Configurações
    assert s["github_url"] is None and s["linkedin_url"] is None
    assert seeded.put("/api/settings/site_url", json={"value": "javascript:alert(1)"}).status_code == 422
    assert seeded.put("/api/settings/site_url", json={"value": "https://exemplo.dev"}).status_code == 200


# --- Notas pelos prints (D17, D18) ---------------------------------------------


def test_aggregate_rule():
    r = lambda n, res: {"question_number": n, "result": res}  # noqa: E731
    # Sem número: erros se juntam ao próximo acerto
    agg = prints.aggregate([r(None, "correct"), r(None, "wrong"), r(None, "wrong"), r(None, "correct"),
                            r(None, "unknown"), r(None, "correct")])
    assert agg == {"total_questions": 3, "first_try_correct": 2, "wrong_attempts": 2, "score": 6.7}
    # Com número
    agg = prints.aggregate([r(1, "correct"), r(2, "wrong"), r(2, "correct"), r(3, "wrong")])
    assert agg == {"total_questions": 3, "first_try_correct": 1, "wrong_attempts": 2, "score": 3.3}


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), "green").save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def materials(tmp_path, monkeypatch):
    root = tmp_path / "materiais"
    (root / "Segurança de Software" / "Lab").mkdir(parents=True)
    for i in range(3):
        (root / "Segurança de Software" / "Lab" / f"print{i}.png").write_bytes(_png())
    (root / "Segurança de Software" / "notas.txt").write_text("não é imagem")
    (tmp_path / "segredo.png").write_bytes(_png())
    monkeypatch.setenv("PAINEL_MATERIALS_DIR", str(root))
    return root


def test_folder_listing_is_confined(seeded, materials):
    client = seeded
    top = client.get("/api/prints/folder").json()
    assert top["entries"] == [{"name": "Segurança de Software", "path": "Segurança de Software", "type": "dir"}]
    inner = client.get("/api/prints/folder", params={"path": "Segurança de Software"}).json()
    assert [e["name"] for e in inner["entries"]] == ["Lab"]  # o .txt não aparece
    for bad in ("..", "../segredo.png", "/etc", "Segurança de Software/../../segredo.png"):
        assert client.get("/api/prints/folder", params={"path": bad}).status_code in (400, 404), bad
    r = client.post("/api/prints/analyze", json={"source": "folder", "paths": ["../segredo.png"]})
    assert r.status_code == 400


def test_analyze_folder_proposes_without_saving(seeded, materials):
    client = seeded
    model = FakeModel(prints_queue=[
        {"question_number": None, "result": "wrong", "note": "vermelho"},
        {"question_number": None, "result": "correct", "note": "verde"},
        {"question_number": None, "result": "correct", "note": "verde"},
    ])
    app.state.llm_transport = httpx.MockTransport(model)
    client.put("/api/settings/default_model", json={"value": "gemma"})
    try:
        r = client.post("/api/prints/analyze", json={"source": "folder", "paths": ["Segurança de Software/Lab"]})
    finally:
        del app.state.llm_transport
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["images"] == 3 and p["total_questions"] == 2 and p["first_try_correct"] == 1
    assert p["wrong_attempts"] == 1 and p["score"] == 5.0
    # A imagem vai para o modelo local como data URL; o texto do sistema é só o prompt
    content = model.requests[0]["messages"][1]["content"]
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    # Nada foi gravado em prazos
    assert all(d["score"] is None for d in client.get("/api/deadlines").json())


def test_analyze_notion_section_downloads_without_token(seeded, monkeypatch):
    client = seeded
    monkeypatch.setenv("NOTION_TOKEN", "ntn_teste")
    _, topics = _seguro_topics(client)
    t = topics[0]
    t["notion_page_id"] = "page-1"
    client.put(f"/api/topics/{t['id']}", json={k: v for k, v in t.items() if k != "id"})

    blocks = {"results": [
        {"id": "h1", "type": "heading_2", "heading_2": {"rich_text": [{"plain_text": "Atividade 1"}]}},
        {"id": "i1", "type": "image", "image": {"type": "file", "file": {"url": "https://s3.example/a.png"}}},
        {"id": "h2", "type": "heading_2", "heading_2": {"rich_text": [{"plain_text": "Laboratório"}]}},
        {"id": "i2", "type": "image", "image": {"type": "file", "file": {"url": "https://s3.example/b.png"}}},
        {"id": "i3", "type": "image", "image": {"type": "external", "external": {"url": "https://s3.example/c.png"}}},
    ], "has_more": False}
    app.state.notion_transport = httpx.MockTransport(lambda req: httpx.Response(200, json=blocks))
    app.state.notion_sleep = lambda s: None
    seen = []

    def images(req):
        seen.append(req)
        return httpx.Response(200, content=_png())

    app.state.image_transport = httpx.MockTransport(images)
    model = FakeModel(prints_queue=[{"question_number": 1, "result": "wrong"}, {"question_number": 1, "result": "correct"}])
    app.state.llm_transport = httpx.MockTransport(model)
    client.put("/api/settings/vision_model", json={"value": "gemma-vision"})
    try:
        secs = client.get("/api/prints/notion-sections", params={"topic_id": t["id"]}).json()
        assert secs == [{"section": "Atividade 1", "images": 1}, {"section": "Laboratório", "images": 2}]
        r = client.post("/api/prints/analyze", json={"source": "notion", "topic_id": t["id"], "section": "Laboratório"})
    finally:
        for k in ("notion_transport", "notion_sleep", "image_transport", "llm_transport"):
            delattr(app.state, k)
    assert r.status_code == 200, r.text
    assert r.json()["total_questions"] == 1 and r.json()["wrong_attempts"] == 1 and r.json()["score"] == 0.0
    # Só as duas imagens da seção, sem o token do Notion no pedido da imagem
    assert [str(x.url) for x in seen] == ["https://s3.example/b.png", "https://s3.example/c.png"]
    assert all("authorization" not in x.headers for x in seen)
    assert model.requests[0]["model"] == "gemma-vision"


def test_check_vision(seeded):
    client = seeded
    client.put("/api/settings/default_model", json={"value": "gemma"})
    for number, ok in ((7, True), (1, False)):
        app.state.llm_transport = httpx.MockTransport(FakeModel(vision_number=number))
        try:
            assert client.post("/api/prints/check-vision", json={}).json()["ok"] is ok
        finally:
            del app.state.llm_transport
