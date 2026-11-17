"""v1.8.2: tarefas que voltavam repetidas, card do dia preso no mesmo card e apagar tema sem histórico."""

from datetime import date, datetime, timedelta

from app import models

DAY = "2026-11-15"


def _topics(client, subject_name):
    with client.session_factory() as s:
        subject = s.query(models.Subject).filter(models.Subject.name == subject_name).one()
        return [(t.id, t.title) for t in sorted(subject.topics, key=lambda t: t.position)]


def _post(client, day, label, **kw):
    return client.post("/api/learning/checklist", json={"day": day, "label": label, **kw}).json()


def test_carry_skips_task_done_on_a_later_day(seeded):
    """Pendente em 13/11 e marcada em 14/11: não volta em 15/11 (o caso real que repetia)."""
    t1 = _topics(seeded, "Engenharia de Requisitos")[0][0]
    label = "Concluir Tema 1 e Tema 2 · Engenharia de Requisitos"
    _post(seeded, "2026-11-12", label, topic_id=t1)
    _post(seeded, "2026-11-13", label, topic_id=t1)
    done = _post(seeded, "2026-11-14", label, topic_id=t1)
    seeded.patch(f"/api/learning/checklist/{done['id']}", json={"done": True})
    _post(seeded, "2026-11-13", "Ler o capítulo 2")  # sem marcar em nenhum dia: continua vindo
    pending = seeded.get("/api/learning/checklist/pending", params={"day": DAY}).json()
    assert [p["label"] for p in pending] == ["Ler o capítulo 2"]


def test_carry_skips_task_whose_topics_are_done_in_portal(seeded):
    topics = _topics(seeded, "Engenharia de Requisitos")
    _post(seeded, "2026-11-14", "Concluir Tema 1 e Tema 2 · Engenharia de Requisitos", topic_id=topics[0][0])
    assert len(seeded.get("/api/learning/checklist/pending", params={"day": DAY}).json()) == 1
    for tid, _ in topics[:2]:
        t = seeded.get(f"/api/topics/{tid}").json()
        seeded.put(f"/api/topics/{tid}", json={**t, "portal_done": True})
    assert seeded.get("/api/learning/checklist/pending", params={"day": DAY}).json() == []
    out = seeded.post("/api/learning/checklist/carry", params={"day": DAY}).json()
    assert out["added"] == 0


def test_label_topics_respects_word_borders(seeded):
    """"Tema 1" não casa com "Tema 10"; títulos com " e " no meio continuam inteiros."""
    topics = _topics(seeded, "Engenharia de Requisitos")
    with seeded.session_factory() as s:
        sid = s.get(models.Topic, topics[0][0]).subject_id
        s.add(models.Topic(subject_id=sid, title="Tema 10", position=10, portal_done=False))
        s.commit()
    item = _post(seeded, DAY, "Concluir Tema 1 e Tema 2 · Engenharia de Requisitos", topic_id=topics[0][0])
    got = seeded.get(f"/api/learning/checklist/{item['id']}/topics").json()
    assert [t["title"] for t in got] == ["Tema 1", "Tema 2"]


def test_tick_task_then_mark_topics_done(seeded):
    """Marcar a tarefa não mexe nos temas; o OK na tela chama topics-done, que marca só os citados."""
    topics = _topics(seeded, "Engenharia de Requisitos")
    item = _post(seeded, DAY, "Concluir Tema 1 e Tema 2 · Engenharia de Requisitos", topic_id=topics[0][0])
    seeded.patch(f"/api/learning/checklist/{item['id']}", json={"done": True})
    assert not seeded.get(f"/api/topics/{topics[0][0]}").json()["portal_done"]
    out = seeded.post(f"/api/learning/checklist/{item['id']}/topics-done").json()
    assert out["marked"] == ["Tema 1", "Tema 2"]
    states = [seeded.get(f"/api/topics/{tid}").json()["portal_done"] for tid, _ in topics[:3]]
    assert states == [True, True, False]
    # Tarefa comum (sem tema): lista vazia, nada marcado
    other = _post(seeded, DAY, "Ler o capítulo 2")
    assert seeded.get(f"/api/learning/checklist/{other['id']}/topics").json() == []
    assert seeded.post(f"/api/learning/checklist/{other['id']}/topics-done").json() == {"marked": []}


def test_plan_does_not_retitle_a_topic_already_on_today(seeded):
    """Com "Concluir Tema 1 e Tema 2" hoje (feita ou não), o Montar o dia não cria "Tema 2 e Tema 3"."""
    topics = _topics(seeded, "Engenharia de Requisitos")
    item = _post(seeded, "2026-11-10", "Concluir Tema 1 e Tema 2 · Engenharia de Requisitos", topic_id=topics[0][0])
    seeded.patch(f"/api/learning/checklist/{item['id']}", json={"done": True})
    t1 = seeded.get(f"/api/topics/{topics[0][0]}").json()
    seeded.put(f"/api/topics/{topics[0][0]}", json={**t1, "portal_done": True})  # só o Tema 1 no portal
    plan = seeded.post("/api/learning/checklist/plan", params={"day": "2026-11-10"}).json()
    labels = [i["label"] for i in plan["items"]]
    assert not any(lbl.startswith("Concluir Tema 2 e Tema 3 · Modelagem") for lbl in labels)


def test_topic_delete_only_without_history(seeded):
    topics = _topics(seeded, "Engenharia de Requisitos")
    with seeded.session_factory() as s:
        sid = s.get(models.Topic, topics[0][0]).subject_id
        extra = models.Topic(subject_id=sid, title="Tema 9", position=9, portal_done=False)
        s.add(extra)
        s.commit()
        extra_id = extra.id
    used = topics[0][0]
    _post(seeded, DAY, "Concluir Tema 1 · Engenharia de Requisitos", topic_id=used)
    r = seeded.delete(f"/api/topics/{used}")
    assert r.status_code == 409 and "1 tarefa(s)" in r.json()["detail"]
    assert seeded.get(f"/api/topics/{used}").status_code == 200
    assert seeded.delete(f"/api/topics/{extra_id}").status_code == 204
    assert seeded.get(f"/api/topics/{extra_id}").status_code == 404


def _card(s, topic_id, front, next_review, **kw):
    c = models.Card(topic_id=topic_id, kind="concept", mode="flip", front=front, back="b", source="text",
                    next_review=next_review, **kw)
    s.add(c)
    return c


def test_card_of_day_rotates_when_nothing_is_due(seeded):
    """Nenhum vencido: entra o revisado há mais tempo, nunca o de ontem (antes voltava sempre o mesmo)."""
    tid = _topics(seeded, "Segurança de Software")[0][0]
    today = date(2026, 11, 15)
    with seeded.session_factory() as s:
        a = _card(s, tid, "Sanitização?", today + timedelta(days=7), step=2, day_card_on=today - timedelta(days=1))
        b = _card(s, tid, "Hash?", today + timedelta(days=3), step=3)
        c = _card(s, tid, "XSS?", today + timedelta(days=5), step=1)
        s.flush()
        s.add(models.CardReview(card_id=a.id, created_at=datetime(2026, 11, 14, 20), mode="flip", knew=True))
        s.add(models.CardReview(card_id=b.id, created_at=datetime(2026, 11, 13, 20), mode="flip", knew=True))
        s.add(models.CardReview(card_id=c.id, created_at=datetime(2026, 11, 10, 20), mode="flip", knew=True))
        s.commit()
    day = seeded.get("/api/cards/today", params={"today": today.isoformat()}).json()
    assert day["card"]["front"] == "XSS?"  # revisado há mais tempo; o de ontem (Sanitização) fica de fora
    nxt = seeded.get("/api/cards/today", params={"today": (today + timedelta(days=1)).isoformat()}).json()
    assert nxt["card"]["front"] != "XSS?"


def test_card_of_day_prefers_due_cards(seeded):
    tid = _topics(seeded, "Segurança de Software")[0][0]
    today = date(2026, 11, 15)
    with seeded.session_factory() as s:
        _card(s, tid, "Ainda não vence", today + timedelta(days=2))
        _card(s, tid, "Vencido", today - timedelta(days=1), step=1)
        s.commit()
    assert seeded.get("/api/cards/today", params={"today": today.isoformat()}).json()["card"]["front"] == "Vencido"


def test_task_history_by_day(client):
    """v1.8.2: as tarefas concluídas (e as não feitas) ficam visíveis por dia, a mais recente primeiro."""
    a = _post(client, "2026-11-14", "Concluir Tema 1")
    client.patch(f"/api/learning/checklist/{a['id']}", json={"done": True})
    _post(client, "2026-11-14", "Ler o capítulo 2")
    _post(client, "2026-11-15", "Revisar cards vencidos (3)")
    _post(client, "2026-07-01", "Velha demais")  # fora dos 120 dias
    _post(client, "2026-11-16", "Amanhã")  # depois do dia pedido
    hist = client.get("/api/learning/checklist/history", params={"day": DAY}).json()
    assert [(d["day"], d["done"], d["total"]) for d in hist] == [("2026-11-15", 0, 1), ("2026-11-14", 1, 2)]
    assert [(t["label"], t["done"]) for t in hist[1]["tasks"]] == [("Concluir Tema 1", True), ("Ler o capítulo 2", False)]
