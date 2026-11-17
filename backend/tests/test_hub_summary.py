"""D45: resumo só de leitura para o hub pessoal (GET /api/hub-summary)."""

import re

KEYS = {"source", "updated_at", "state", "next_step", "deadlines", "alerts"}


def test_hub_summary_empty_database(client):
    r = client.get("/api/hub-summary")
    assert r.status_code == 200
    data = r.json()
    assert set(data) == KEYS
    assert data["source"] == "painel"
    assert data["state"] == "" and data["next_step"] == ""
    assert data["deadlines"] == [] and data["alerts"] == []
    # data e hora com fuso, ex.: 2026-11-14T10:00:00-03:00
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}", data["updated_at"])


def test_hub_summary_with_data(seeded):
    seeded.post("/api/study-sessions", json={"started_at": "2026-11-10T08:00:00", "seconds": 5400})
    data = seeded.get("/api/hub-summary", params={"today": "2026-11-10"}).json()
    assert set(data) == KEYS

    # Mesma próxima ação da tela inicial
    action = seeded.get("/api/overview", params={"today": "2026-11-10"}).json()["next_action"]
    assert data["next_step"] == f"{', '.join(action['steps'])} ({action['subject_name']})"

    assert data["state"].startswith("1h30 estudadas na semana")
    assert "tema(s) pendente(s)" in data["state"]

    # Prazos: 30 dias, data AAAA-MM-DD, prova com horário no título
    assert all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", d["date"]) and d["title"] for d in data["deadlines"])
    assert {"date": "2026-11-17", "title": "Prova de Engenharia de Requisitos 17:00"} in data["deadlines"]
    assert max(d["date"] for d in data["deadlines"]) < "2026-12-10"

    # Alerta de prova em até 7 dias; no máximo 5 alertas, todos texto
    assert "Prova de Engenharia de Requisitos em 7 dias" in data["alerts"]
    assert len(data["alerts"]) <= 5 and all(isinstance(a, str) for a in data["alerts"])


def test_hub_summary_has_no_grades(seeded):
    # Notas nunca saem para o hub: põe uma nota alta e confere que nada dela aparece
    with seeded.session_factory() as s:
        from app import models

        exam = s.query(models.Exam).first()
        exam.score = 9.7
        s.commit()
    text = seeded.get("/api/hub-summary", params={"today": "2026-11-10"}).text
    assert "9.7" not in text and "9,7" not in text and "nota" not in text.lower()


def test_hub_summary_overdue_deadline_alert(seeded):
    with seeded.session_factory() as s:
        from datetime import date

        from app import models

        s.add(models.Deadline(title="Entregar trabalho", due_date=date(2026, 11, 5), kind="task"))
        s.commit()
    alerts = seeded.get("/api/hub-summary", params={"today": "2026-11-10"}).json()["alerts"]
    assert any("prazo(s) passado(s)" in a for a in alerts)


def test_hub_reaches_painel_from_docker_by_default():
    # O hub no Docker chama http://host.docker.internal:8000; o nome precisa estar na lista padrão
    from app.main import DEFAULT_ALLOWED_HOSTS

    assert "host.docker.internal" in DEFAULT_ALLOWED_HOSTS.split(",")
    assert "evil.example" not in DEFAULT_ALLOWED_HOSTS


def test_hub_summary_is_read_only(client):
    assert client.post("/api/hub-summary").status_code == 405
