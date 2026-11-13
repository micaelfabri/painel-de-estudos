"""v1.8: cursos e certificados fora da faculdade (SPEC §18, D38–D44)."""

from datetime import date, datetime, timedelta

from tests.test_v13_study import TOPIC_TEXT, _answer_all, _seguro_topics, fake  # noqa: F401

TODAY = date.today()


def _course(client, **kw):
    body = {"name": "Google Data Analytics", "platform": "Coursera", "course_type": "course_certificate",
            "modules": 9, "total_hours": 180, **kw}
    r = client.post("/api/courses", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_k1_course_with_modules_is_separate_from_the_college(seeded):
    """K1: curso com 9 módulos aparece em "Fazendo" com 0% e não aparece no Painel da faculdade."""
    c = _course(seeded)
    assert c["modules_total"] == 9 and c["progress"] == 0 and c["course_status"] == "doing"
    assert [m["name"] for m in c["modules"]][:2] == ["Módulo 1", "Módulo 2"]
    doing = seeded.get("/api/courses", params={"status": "doing"}).json()
    assert [x["name"] for x in doing] == ["Google Data Analytics"]
    overview = seeded.get("/api/overview").json()
    assert all(s["name"] != "Módulo 1" for s in overview["subjects"])
    # A página de progresso do curso (AAC) continua na graduação
    assert seeded.get("/api/course/progress").json()["degree"]["name"] != "Google Data Analytics"
    assert seeded.get("/api/courses/summary").json()["counts"]["doing"] == 1


def test_course_validation(seeded):
    assert seeded.post("/api/courses", json={"name": "X", "url": "http://inseguro.com"}).status_code == 422
    assert seeded.post("/api/courses", json={"name": "X", "notion_page": "não é link"}).status_code == 422
    ok = seeded.post("/api/courses", json={
        "name": "X", "notion_page": "https://www.notion.so/Minha-pagina-0123456789abcdef0123456789abcdef"}).json()
    assert ok["notion_page_id"] == "0123456789abcdef0123456789abcdef"
    # Sem módulos: progresso manual
    lang = seeded.post("/api/courses", json={"name": "Inglês", "course_type": "language", "manual_progress": 35}).json()
    assert lang["modules_total"] == 0 and lang["progress"] == 35


def test_k2_hours_and_tests_stay_in_their_area(fake):  # noqa: F811
    """K2: 20 min num módulo contam em cursos e não na semana da faculdade; teste numa aula só em Cursos › Histórico."""
    client, _ = fake
    c = _course(client)
    module = c["modules"][0]
    lesson = client.post(f"/api/courses/modules/{module['id']}/lessons", json={"title": "Integridade dos dados"}).json()
    before = client.get("/api/overview").json()["week"]["total_seconds"]
    now = datetime.now().replace(microsecond=0)
    client.post("/api/study-sessions", json={"subject_id": module["id"], "seconds": 1200,
                                             "started_at": (now - timedelta(minutes=20)).isoformat(),
                                             "ended_at": now.isoformat()})
    assert client.get("/api/overview").json()["week"]["total_seconds"] == before
    summary = client.get("/api/courses/summary").json()
    assert summary["week_seconds"] == 1200 and summary["goal_hours"] == 5.0
    assert client.get("/api/courses").json()[0]["week_seconds"] == 1200

    qs = client.post("/api/agent/question-sets", json={"topic_id": lesson["id"], "text": TOPIC_TEXT, "n_options": 5}).json()
    _answer_all(client, qs, right=8)
    assert [r["id"] for r in client.get("/api/study/history", params={"area": "cursos"}).json()] == [qs["id"]]
    assert qs["id"] not in [r["id"] for r in client.get("/api/study/history").json()]
    assert [t["topic_id"] for t in client.get("/api/study/history/topics", params={"area": "cursos"}).json()] == [lesson["id"]]
    m = client.get("/api/study/metrics", params={"area": "cursos"}).json()
    assert m["totals"]["sets"] == 1 and m["totals"]["seconds"] == 1200
    assert client.get("/api/study/metrics").json()["totals"]["sets"] == 0
    # Erros: 2 na área de cursos, nenhum na faculdade
    assert len(client.get("/api/learning/mistakes", params={"area": "cursos"}).json()) == 2
    assert client.get("/api/learning/mistakes/summary", params={"area": "faculdade"}).json()["open"] == 0
    detail = client.get(f"/api/courses/{c['id']}").json()
    assert detail["sets"] == 1 and detail["average_score"] == 0.8


def test_lessons_complete_the_module_and_next_lesson(seeded):
    c = _course(seeded, modules=2)
    m1, m2 = c["modules"]
    a = seeded.post(f"/api/courses/modules/{m1['id']}/lessons", json={"title": "Aula 1"}).json()
    b = seeded.post(f"/api/courses/modules/{m1['id']}/lessons", json={"title": "Aula 2"}).json()
    assert seeded.get(f"/api/courses/{c['id']}").json()["next_lesson"]["title"] == "Aula 1"
    assert seeded.patch(f"/api/courses/lessons/{a['id']}", json={"done": True}).json()["module_status"] == "in_progress"
    assert seeded.patch(f"/api/courses/lessons/{b['id']}", json={"done": True}).json()["module_status"] == "passed"
    detail = seeded.get(f"/api/courses/{c['id']}").json()
    assert detail["modules_done"] == 1 and detail["progress"] == 50
    assert detail["next_lesson"]["module_id"] == m2["id"]
    # A aula da faculdade não pode ser mexida por aqui
    _, topics = _seguro_topics(seeded)
    assert seeded.patch(f"/api/courses/lessons/{topics[0]['id']}", json={"done": True}).status_code == 404


def test_d40_courses_enter_the_day_plan_only_with_the_switch(seeded):
    c = _course(seeded, modules=1)
    seeded.post(f"/api/courses/modules/{c['modules'][0]['id']}/lessons", json={"title": "Limpeza com SQL"})
    labels = [i["label"] for i in seeded.post("/api/learning/checklist/plan").json()["items"]]
    assert not any("Limpeza com SQL" in x for x in labels)
    seeded.put("/api/settings/courses_in_day_plan", json={"value": True})
    labels = [i["label"] for i in seeded.post("/api/learning/checklist/plan").json()["items"]]
    assert "Próxima aula: Limpeza com SQL · Google Data Analytics" in labels


def test_k3_acc_bridge_once(seeded):
    """K3: curso concluído que conta como AAC cria uma atividade com as horas dele, uma vez só."""
    c = _course(seeded, counts_acc=True, acc_category="Cursos", total_hours=40)
    assert seeded.post(f"/api/courses/{c['id']}/acc").status_code == 409  # ainda não concluído
    body = {k: c[k] for k in ("name", "platform", "course_type", "total_hours", "counts_acc", "acc_category")}
    seeded.put(f"/api/courses/{c['id']}", json={**body, "course_status": "done"})
    before = seeded.get("/api/course/progress").json()["acc"]["counted_hours"]
    out = seeded.post(f"/api/courses/{c['id']}/acc").json()
    assert out["title"] == "Coursera - Google Data Analytics" and out["hours"] == 40
    assert seeded.get("/api/course/progress").json()["acc"]["counted_hours"] == before + 40
    assert seeded.post(f"/api/courses/{c['id']}/acc").status_code == 409
    detail = seeded.get(f"/api/courses/{c['id']}").json()
    assert detail["acc_activity_id"] == out["acc_activity_id"] and detail["progress"] == 100
    s = seeded.get("/api/courses/summary").json()
    assert s["certificates"] == 1 and s["acc_hours"] == 40


def test_certification_exam_only_in_courses_area(seeded):
    """D42: a prova de certificação fica só na área de cursos."""
    exam = (datetime.now() + timedelta(days=30)).replace(microsecond=0)
    _course(seeded, name="AWS Cloud Practitioner", course_type="certification", exam_at=exam.isoformat(), modules=4)
    nxt = seeded.get("/api/courses/summary").json()["next_exam"]
    assert nxt["name"] == "AWS Cloud Practitioner" and nxt["days"] == 30
    assert all("AWS" not in e["subject_name"] for e in seeded.get("/api/overview").json()["upcoming_exams"])
    assert "AWS" not in str(seeded.get("/api/study/agenda").json())


def test_timer_modules_and_delete_course(seeded):
    c = _course(seeded, modules=2)
    mods = seeded.get("/api/courses/modules").json()
    assert [m["course_name"] for m in mods] == ["Google Data Analytics"] * 2
    assert seeded.delete(f"/api/courses/{c['id']}").status_code == 204
    assert seeded.get("/api/courses").json() == []
    assert seeded.get(f"/api/courses/{c['id']}").status_code == 404
