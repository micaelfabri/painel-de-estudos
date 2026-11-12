"""Testes da F1: cadastros, carga inicial, progresso do portal, regras e configurações."""

import pytest

from app.grading import PRESETS, GradeInput, GradingRule, evaluate


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_register_current_semester_and_see_it_saved(client):
    """Linha "pronto quando" da F1: cadastrar o semestre atual e ver salvo."""
    degree = client.post("/api/degrees", json={"name": "Engenharia de Software", "institution": "Universidade Exemplo"}).json()
    sem = client.post("/api/semesters", json={"degree_id": degree["id"], "code": "2026.3", "is_current": True})
    assert sem.status_code == 201
    subj = client.post(
        "/api/subjects",
        json={
            "degree_id": degree["id"],
            "semester_id": sem.json()["id"],
            "name": "Engenharia de Requisitos",
            "hours": 80,
            "grading_rule": PRESETS["padrao_2026"],
        },
    )
    assert subj.status_code == 201
    listed = client.get("/api/subjects", params={"semester_id": sem.json()["id"]}).json()
    assert [s["name"] for s in listed] == ["Engenharia de Requisitos"]


def test_duplicate_semester_code_is_conflict(client):
    degree = client.post("/api/degrees", json={"name": "X"}).json()
    client.post("/api/semesters", json={"degree_id": degree["id"], "code": "2026.3"})
    dup = client.post("/api/semesters", json={"degree_id": degree["id"], "code": "2026.3"})
    assert dup.status_code == 409


def test_invalid_grading_rule_rejected(client):
    degree = client.post("/api/degrees", json={"name": "X"}).json()
    bad = client.post("/api/subjects", json={"degree_id": degree["id"], "name": "Y", "grading_rule": {"parts": []}})
    assert bad.status_code == 422


def test_seed_matches_spec(seeded):
    subjects = seeded.get("/api/subjects").json()
    current = [s for s in subjects if s["semester_id"] is not None]
    pending = [s for s in subjects if s["semester_id"] is None]
    assert len(current) == 5
    assert len(pending) == 16

    seguro = next(s for s in current if s["name"] == "Segurança de Software")
    assert seguro["exam_requires_lab"] is True
    exam = seeded.get("/api/exams", params={"subject_id": seguro["id"]}).json()[0]
    assert exam["scheduled_at"] is None and exam["schedule_by"] == "2026-11-22"

    progress = seeded.get(f"/api/subjects/{seguro['id']}/portal-progress").json()
    assert progress["percent"] == 33 and progress["lab_total"] == 1

    topics = seeded.get("/api/topics", params={"subject_id": seguro["id"]}).json()
    assert [t["portal_done"] for t in topics] == [True, True, True, False, False]

    acc = seeded.get("/api/acc-activities").json()
    assert sum(a["hours"] for a in acc) == 16

    comps = {c["name"]: c for c in seeded.get("/api/degree-components").json()}
    assert comps["Optativa"]["to_check"] is True
    assert sum(c["done_hours"] for c in comps.values()) == 1200


def test_portal_progress_upsert(seeded):
    subj = seeded.get("/api/subjects").json()[0]
    r = seeded.put(f"/api/subjects/{subj['id']}/portal-progress", json={"percent": 50, "contents_done": 4})
    assert r.status_code == 200 and r.json()["percent"] == 50
    assert seeded.put(f"/api/subjects/{subj['id']}/portal-progress", json={"percent": 150}).status_code == 422


def test_settings_defaults_and_validation(client):
    values = client.get("/api/settings").json()["values"]
    assert values["timer_goal_minutes"] == 90 and values["timer_alarm_minutes"] == 120
    assert values["options_per_question"] is None
    assert client.put("/api/settings/weekly_hours_goal", json={"value": 19}).status_code == 200
    assert client.put("/api/settings/timer_goal_minutes", json={"value": "abc"}).status_code == 422
    assert client.put("/api/settings/unknown", json={"value": 1}).status_code == 404


# --- Motor de regras ---------------------------------------------------------


def rule(name):
    return GradingRule.model_validate(PRESETS[name])


def test_standard_rule_pass_and_fail():
    assert evaluate(rule("padrao_2026"), GradeInput(scores={"av": 5, "pa": 1.5})).passed is True
    assert evaluate(rule("padrao_2026"), GradeInput(scores={"av": 4, "pa": 1.5})).passed is False


def test_missing_score_is_undecided():
    assert evaluate(rule("padrao_2026"), GradeInput(scores={"av": 7})).passed is None


def test_out_of_range_score_raises():
    with pytest.raises(ValueError):
        evaluate(rule("padrao_2026"), GradeInput(scores={"av": 9, "pa": 1}))


def test_ap_counts_only_with_av_at_least_4():
    r = rule("arquitetura_sistemas")
    low = evaluate(r, GradeInput(scores={"av": 3.5, "ap": 2}))
    assert low.total == 3.5 and "ap" in low.ignored and low.passed is False
    high = evaluate(r, GradeInput(scores={"av": 4.5, "ap": 2}))
    assert high.total == 6.5 and high.passed is True


def test_attendance_rule():
    r = rule("padroes_java")
    assert evaluate(r, GradeInput(scores={"av": 8}, attendance=0.7)).passed is False
    assert evaluate(r, GradeInput(scores={"av": 8}, attendance=0.8)).passed is True
    assert evaluate(r, GradeInput(scores={"av": 8})).passed is None


def test_grade_check_endpoint(seeded):
    java = next(s for s in seeded.get("/api/subjects").json() if s["name"] == "Padrões de Projeto")
    r = seeded.post(f"/api/subjects/{java['id']}/grade-check", json={"scores": {"av": 7}, "attendance": 0.9})
    assert r.status_code == 200 and r.json()["passed"] is True
