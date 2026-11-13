"""Testes da F3: cliente do modelo (com modelo falso), questões, correção, erros, conversa, uso."""

import json

import httpx
import pytest

from app.agent import prompts
from app.main import app

TOPIC_TEXT = "Autenticação verifica a identidade do usuário. Autorização define o que ele pode acessar."


def _questions(n, n_options):
    return [
        {
            "statement": f"Questão {i}?",
            "options": [f"opção {j}" for j in range(n_options)],
            "correct_index": 0,
            "explanation": "Está no texto.",
        }
        for i in range(n)
    ]


class FakeModel:
    """Modelo falso no lugar do Ollama: responde conforme o prompt e registra o que recebeu."""

    def __init__(self, bad_replies=0, fail=False):
        self.bad_replies = bad_replies
        self.fail = fail
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if self.fail:
            raise httpx.ConnectError("conexão recusada", request=request)
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "qwen3.5:9b"}, {"id": "gemma4:12b"}]})
        body = json.loads(request.content)
        self.requests.append(body)
        system = body["messages"][0]["content"]
        if self.bad_replies > 0:
            self.bad_replies -= 1
            content = "Claro! Aqui estão as questões: (sem JSON)"
        elif "múltipla escolha" in system:
            n_options = int(system.split("com exatamente ")[1].split(" ")[0])
            content = json.dumps({"summary": "Resumo curto.", "questions": _questions(10, n_options)})
        else:
            content = "```json\n" + json.dumps({"answer": "Autorização vem depois da autenticação."}) + "\n```"
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        })


@pytest.fixture()
def fake(seeded):
    model = FakeModel()
    app.state.llm_transport = httpx.MockTransport(model)
    seeded.put("/api/settings/default_model", json={"value": "qwen3.5:9b"})
    yield seeded, model
    del app.state.llm_transport


def _topic_id(client):
    seguro = next(s for s in client.get("/api/subjects").json() if s["name"] == "Segurança de Software")
    return client.get("/api/topics", params={"subject_id": seguro["id"]}).json()[3]["id"]  # Tema 4


def test_prompts_are_versioned():
    p = prompts.load("generate_questions")
    assert p.version == "v2" and "{text}" in p.template and "{avoid}" in p.template


def test_models_list(fake):
    client, _ = fake
    data = client.get("/api/agent/models").json()
    assert data["reachable"] and data["models"] == ["gemma4:12b", "qwen3.5:9b"]
    assert data["default_model"] == "qwen3.5:9b"


def test_models_offline(seeded):
    app.state.llm_transport = httpx.MockTransport(FakeModel(fail=True))
    try:
        data = seeded.get("/api/agent/models").json()
        assert data["reachable"] is False and "fora do ar" in data["error"]
    finally:
        del app.state.llm_transport


def test_full_cycle_generate_answer_score(fake):
    client, model = fake
    topic_id = _topic_id(client)
    r = client.post("/api/agent/question-sets", json={"topic_id": topic_id, "text": TOPIC_TEXT, "n_options": 5})
    assert r.status_code == 201, r.text
    qs = r.json()
    assert qs["summary"] == "Resumo curto." and len(qs["questions"]) == 10
    assert qs["prompt_version"] == "generate_questions.v2" and qs["model"] == "qwen3.5:9b"
    assert all(len(q["options"]) == 5 for q in qs["questions"])
    # A correta não vai para a tela antes de responder
    assert all(q["answer"] is None for q in qs["questions"])
    # Só o texto do tema vai ao modelo: nada de notas ou dados pessoais
    sent = model.requests[0]["messages"][0]["content"]
    assert TOPIC_TEXT in sent and "Polo Centro" not in sent

    # 7 certas, 3 erradas -> 70%
    mistakes = []
    for i, q in enumerate(qs["questions"]):
        res = client.post(f"/api/agent/questions/{q['id']}/answer", json={"chosen_index": 0 if i < 7 else 1}).json()
        if res["mistake_id"]:
            mistakes.append(res["mistake_id"])
    assert res["set_completed"] and res["set_score"] == pytest.approx(0.7)
    assert len(mistakes) == 3

    # Responder de novo é conflito
    assert client.post(f"/api/agent/questions/{qs['questions'][0]['id']}/answer", json={"chosen_index": 0}).status_code == 409

    # Minuto do vídeo no erro
    m = client.get(f"/api/mistakes/{mistakes[0]}").json()
    m["video_minute"] = "05:40"
    assert client.put(f"/api/mistakes/{mistakes[0]}", json=m).json()["video_minute"] == "05:40"

    # Questão ruim não conta: marcar uma errada -> 7 de 9
    flagged = client.post(f"/api/agent/questions/{qs['questions'][9]['id']}/flag").json()
    assert flagged["set_score"] == pytest.approx(7 / 9)

    # O texto colado fica guardado no tema
    assert client.get(f"/api/topics/{topic_id}").json()["source_text"] == TOPIC_TEXT

    # Registro de uso
    usage = client.get("/api/agent/usage").json()["items"]
    assert usage[0]["status"] == "ok" and usage[0]["input_tokens"] == 100


def test_invalid_json_retries_once_then_ok(fake):
    client, model = fake
    model.bad_replies = 1
    r = client.post("/api/agent/question-sets", json={"topic_id": _topic_id(client), "text": TOPIC_TEXT, "n_options": 4})
    assert r.status_code == 201
    assert client.get("/api/agent/usage").json()["items"][0]["attempts"] == 2


def test_invalid_json_twice_saves_nothing(fake):
    client, model = fake
    model.bad_replies = 2
    r = client.post("/api/agent/question-sets", json={"topic_id": _topic_id(client), "text": TOPIC_TEXT, "n_options": 4})
    assert r.status_code == 502 and r.json()["detail"]["status"] == "invalid_json"
    assert client.get("/api/agent/question-sets").json() == []
    assert client.get("/api/agent/usage").json()["items"][0]["status"] == "invalid_json"


def test_requires_text_and_model(seeded):
    topic_id = _topic_id(seeded)
    r = seeded.post("/api/agent/question-sets", json={"topic_id": topic_id, "n_options": 4})
    assert r.status_code == 422 and r.json()["detail"]["status"] == "no_text"
    r = seeded.post("/api/agent/question-sets", json={"topic_id": topic_id, "text": TOPIC_TEXT, "n_options": 4})
    assert r.status_code == 422 and r.json()["detail"]["status"] == "no_model"


def test_chat_uses_topic_text(fake):
    client, model = fake
    topic_id = _topic_id(client)
    client.post("/api/agent/question-sets", json={"topic_id": topic_id, "text": TOPIC_TEXT, "n_options": 4})
    r = client.post("/api/agent/chat", json={"message": "Qual a diferença?", "topic_id": topic_id,
                                             "history": [{"role": "user", "content": "oi"}, {"role": "assistant", "content": "olá"}]})
    assert r.status_code == 200 and r.json()["answer"].startswith("Autorização")
    last = model.requests[-1]["messages"]
    assert TOPIC_TEXT in last[0]["content"] and last[-1]["content"] == "Qual a diferença?"


def test_server_without_json_mode_falls_back(seeded):
    """LM Studio pode recusar response_format json_object: o cliente repete sem ele."""
    inner = FakeModel()

    def handler(request):
        if request.url.path.endswith("/chat/completions") and "response_format" in json.loads(request.content):
            return httpx.Response(400, json={"error": "response_format.type must be json_schema"})
        return inner(request)

    app.state.llm_transport = httpx.MockTransport(handler)
    try:
        seeded.put("/api/settings/default_model", json={"value": "gemma4:12b"})
        r = seeded.post("/api/agent/question-sets", json={"topic_id": _topic_id(seeded), "text": TOPIC_TEXT, "n_options": 4})
        assert r.status_code == 201, r.text
    finally:
        del app.state.llm_transport


@pytest.mark.parametrize("body", [b'{"object": "list", "data": null}', b"<html>LM</html>", b"[]"])
def test_models_empty_or_odd_reply(seeded, body):
    # Ollama sem modelos responde data: null; outro programa na porta pode responder HTML
    app.state.llm_transport = httpx.MockTransport(lambda req: httpx.Response(200, content=body))
    try:
        r = seeded.get("/api/agent/models")
        assert r.status_code == 200
        data = r.json()
        assert data["models"] == []
        if body.startswith(b"<"):
            assert data["reachable"] is False and "compatível com OpenAI" in data["error"]
        else:
            assert data["reachable"] is True
    finally:
        del app.state.llm_transport


@pytest.mark.parametrize("message", [
    {"content": '{"summary": "abc", "questions": [', "finish_reason": "length"},
    {"content": "", "reasoning_content": "pensando...", "finish_reason": "stop"},
])
def test_cut_off_reply_is_not_retried(seeded, message):
    # Resposta cortada pelo contexto (ou só raciocínio): erro claro, sem nova tentativa
    calls = []

    def handler(request):
        if request.url.path.endswith("/chat/completions"):
            calls.append(1)
            finish = message.pop("finish_reason", "stop")
            message.setdefault("finish_reason", finish)
            return httpx.Response(200, json={"choices": [{"message": {k: v for k, v in message.items()
                                                                        if k != "finish_reason"},
                                                          "finish_reason": finish}],
                                             "usage": {"prompt_tokens": 7000, "completion_tokens": 1190}})
        return httpx.Response(200, json={"data": [{"id": "m"}]})

    app.state.llm_transport = httpx.MockTransport(handler)
    seeded.put("/api/settings/default_model", json={"value": "m"})
    try:
        r = seeded.post("/api/agent/question-sets",
                        json={"topic_id": _topic_id(seeded), "text": TOPIC_TEXT, "n_options": 4})
        assert r.status_code == 502
        assert r.json()["detail"]["status"] == "cut_off" and "Context Length" in r.json()["detail"]["message"]
        assert len(calls) == 1
        log = seeded.get("/api/agent/usage").json()["items"]
        entry = log[0] if isinstance(log, list) else log["calls"][0]
        assert "cortada" in (entry.get("error") or "")
    finally:
        del app.state.llm_transport


def _with_400(rule):
    """Envolve o FakeModel: `rule(payload)` devolve uma mensagem de erro 400 ou None."""
    inner = FakeModel()
    sent = []

    def handler(request):
        if request.url.path.endswith("/chat/completions"):
            payload = json.loads(request.content)
            sent.append((payload.get("response_format") or {}).get("type"))
            message = rule(payload)
            if message:
                return httpx.Response(400, json={"error": message})
        return inner(request)

    return handler, sent


def _generate(client):
    return client.post("/api/agent/question-sets",
                       json={"topic_id": _topic_id(client), "text": TOPIC_TEXT, "n_options": 4})


def test_lm_studio_json_schema_is_tried_first(seeded):
    # LM Studio: aceita json_schema e recusa json_object; não deve haver 400 nenhum
    handler, sent = _with_400(lambda p: "'response_format.type' must be 'json_schema' or 'text'"
                              if (p.get("response_format") or {}).get("type") == "json_object" else None)
    app.state.llm_transport = httpx.MockTransport(handler)
    seeded.put("/api/settings/default_model", json={"value": "qwen3.5:9b"})
    try:
        assert _generate(seeded).status_code == 201
        assert sent == ["json_schema"]
    finally:
        del app.state.llm_transport


def test_context_overflow_400_gives_clear_message(seeded):
    handler, sent = _with_400(lambda p: "The number of tokens to keep from the initial prompt is greater "
                                        "than the context length. Try to load the model with a larger context length")
    app.state.llm_transport = httpx.MockTransport(handler)
    seeded.put("/api/settings/default_model", json={"value": "qwen3.5:9b"})
    try:
        r = _generate(seeded)
        assert r.status_code == 502 and r.json()["detail"]["status"] == "cut_off"
        assert sent == ["json_schema"]  # não insiste com outros formatos
    finally:
        del app.state.llm_transport


def test_other_400_shows_server_reason(seeded):
    handler, sent = _with_400(lambda p: "Model qwen3.5:9b is not loaded")
    app.state.llm_transport = httpx.MockTransport(handler)
    seeded.put("/api/settings/default_model", json={"value": "qwen3.5:9b"})
    try:
        r = _generate(seeded)
        assert r.status_code == 502 and "not loaded" in r.json()["detail"]["message"]
        assert sent == ["json_schema", "json_object", None]
    finally:
        del app.state.llm_transport


def test_generation_sends_a_user_message(fake):
    # Qwen no LM Studio recusa conversa só com "system" ("No user query found in messages")
    client, model = fake
    client.post("/api/agent/question-sets", json={"topic_id": _topic_id(client), "text": TOPIC_TEXT, "n_options": 4})
    roles = [m["role"] for m in model.requests[-1]["messages"]]
    assert roles[0] == "system" and "user" in roles


def test_options_are_shuffled_and_answer_follows(fake):
    client, _ = fake
    app.state.shuffle_options = True
    try:
        qs = client.post("/api/agent/question-sets",
                         json={"topic_id": _topic_id(client), "text": TOPIC_TEXT, "n_options": 4}).json()
        positions = []
        for q in qs["questions"]:
            # O modelo falso sempre põe a certa em "opção 0"; depois de embaralhar ela muda de lugar
            idx = q["options"].index("opção 0")
            out = client.post(f"/api/agent/questions/{q['id']}/answer", json={"chosen_index": idx}).json()
            assert out["is_correct"] and out["correct_index"] == idx
            positions.append(idx)
        assert len(set(positions)) > 1
    finally:
        app.state.shuffle_options = False


def test_wrong_counts_are_rejected_by_schema():
    from app.agent.router import set_schema

    schema = set_schema(10, 5)
    q = {"statement": "Pergunta?", "options": ["a", "b", "c", "d"], "correct_index": 0}
    with pytest.raises(Exception):
        schema.model_validate({"summary": "resumo", "questions": [q] * 10})  # 4 alternativas
    q5 = {**q, "options": ["a", "b", "c", "d", "e"]}
    with pytest.raises(Exception):
        schema.model_validate({"summary": "resumo", "questions": [q5] * 9})  # 9 questões
    assert len(schema.model_validate({"summary": "resumo", "questions": [q5] * 10}).questions) == 10
    assert schema.model_json_schema()["properties"]["questions"]["minItems"] == 10
