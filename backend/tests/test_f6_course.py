"""Testes da F6: progresso do curso por componente e ACC contra as 100h."""

import pytest


def test_course_progress_matches_history(seeded):
    data = seeded.get("/api/course/progress").json()
    comps = {c["name"]: c for c in data["components"]}
    # Linha de base do histórico (fictício): 1.200h
    assert data["done_hours"] == 1200 and data["degree"]["total_hours"] == 3200
    assert comps["AAC"]["kind"] == "acc" and comps["AAC"]["done_hours"] == 16
    assert comps["Optativa"]["to_check"] is True
    assert comps["Estágio"]["required_hours"] is None
    assert len(data["unscheduled"]) == 16
    assert data["semesters"][0]["code"] == "2026.3" and len(data["semesters"][0]["subjects"]) == 5


def test_passed_subject_counts_in_its_component(seeded):
    subj = next(s for s in seeded.get("/api/subjects").json() if s["name"] == "Engenharia de Requisitos")
    subj["status"] = "passed"
    seeded.put(f"/api/subjects/{subj['id']}", json=subj)
    comps = {c["name"]: c for c in seeded.get("/api/course/progress").json()["components"]}
    assert comps["Mínima"]["done_hours"] == 1040 + 80 and comps["Mínima"]["from_panel_hours"] == 80


def test_acc_sum_planned_and_category_caps(seeded):
    degree_id = seeded.get("/api/degrees").json()[0]["id"]
    seeded.post("/api/acc-activities", json={"degree_id": degree_id, "title": "Curso Google Data Analytics",
                                            "category": "Cursos", "hours": 40, "activity_date": "2026-09-01"})
    seeded.post("/api/acc-activities", json={"degree_id": degree_id, "title": "Palestra", "category": "Eventos",
                                            "hours": 4, "status": "planned"})
    acc = seeded.get("/api/course/progress").json()["acc"]
    assert acc["counted_hours"] == 56 and acc["planned_hours"] == 4 and acc["missing_hours"] == 44
    assert acc["rules_known"] is False

    # Regra por categoria (quando o regulamento chegar): teto de 30h em Cursos
    seeded.post("/api/acc-rules", json={"degree_id": degree_id, "category": "Cursos", "max_hours": 30})
    acc = seeded.get("/api/course/progress").json()["acc"]
    cursos = next(c for c in acc["categories"] if c["category"] == "Cursos")
    assert cursos["registered"] == 40 and cursos["counted"] == 30 and acc["counted_hours"] == pytest.approx(46)


def test_acc_activity_validation(seeded):
    degree_id = seeded.get("/api/degrees").json()[0]["id"]
    r = seeded.post("/api/acc-activities", json={"degree_id": degree_id, "title": "x", "hours": 0})
    assert r.status_code == 422


def test_acc_activity_delete_updates_total(seeded):
    """v1.7.2: excluir uma atividade tira as horas dela do total de ACC."""
    degree_id = seeded.get("/api/degrees").json()[0]["id"]
    before = seeded.get("/api/course/progress").json()["acc"]["counted_hours"]
    item = seeded.post("/api/acc-activities", json={"degree_id": degree_id, "title": "Minicurso", "hours": 10}).json()
    assert seeded.get("/api/course/progress").json()["acc"]["counted_hours"] == before + 10
    assert seeded.delete(f"/api/acc-activities/{item['id']}").status_code == 204
    assert seeded.get("/api/course/progress").json()["acc"]["counted_hours"] == before
    assert seeded.delete(f"/api/acc-activities/{item['id']}").status_code == 404
