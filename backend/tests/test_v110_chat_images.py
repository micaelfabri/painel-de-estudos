"""v1.10 (D52): prints na conversa com o agente, só para o modelo local, sem guardar a imagem."""

import base64
import io

from PIL import Image

from tests.test_f3_agent import fake  # noqa: F401 (fixture)


def _png(w=2000, h=1000) -> str:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (255, 255, 255)).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def test_chat_sends_reduced_image_to_vision_model_and_saves_only_text(fake):  # noqa: F811
    client, model = fake
    client.put("/api/settings/vision_model", json={"value": "gemma-visao"})
    r = client.post("/api/agent/chat", json={"message": "O que diz este print?", "images": [_png()]})
    assert r.status_code == 200, r.text
    sent = model.requests[-1]
    assert sent["model"] == "gemma-visao"  # sem modelo na tela: o de visão das Configurações
    content = sent["messages"][-1]["content"]
    assert content[0] == {"type": "text", "text": "O que diz este print?"}
    url = content[1]["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,")
    img = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))
    assert max(img.size) == 1280  # reduzida como os prints
    saved = client.get("/api/agent/chat/messages").json()
    assert saved[-2]["content"] == "O que diz este print?\n[1 imagem(ns) enviada(s)]"
    assert "base64" not in str(saved)


def test_chat_model_chosen_on_screen_wins(fake):  # noqa: F811
    client, model = fake
    client.put("/api/settings/vision_model", json={"value": "gemma-visao"})
    client.post("/api/agent/chat", json={"message": "e aqui?", "images": [_png(10, 10)], "model": "outro"})
    assert model.requests[-1]["model"] == "outro"


def test_chat_rejects_non_images_and_too_many(fake):  # noqa: F811
    client, _ = fake
    pdf = "data:application/pdf;base64," + base64.b64encode(b"%PDF").decode()
    assert client.post("/api/agent/chat", json={"message": "x", "images": [pdf]}).status_code == 422
    broken = "data:image/png;base64," + base64.b64encode(b"nao e imagem").decode()
    r = client.post("/api/agent/chat", json={"message": "x", "images": [broken]})
    assert r.status_code == 422 and r.json()["detail"]["status"] == "bad_image"
    four = [_png(10, 10)] * 4
    assert client.post("/api/agent/chat", json={"message": "x", "images": four}).status_code == 422


def test_chat_without_image_unchanged(fake):  # noqa: F811
    client, model = fake
    client.post("/api/agent/chat", json={"message": "só texto"})
    assert model.requests[-1]["messages"][-1]["content"] == "só texto"
