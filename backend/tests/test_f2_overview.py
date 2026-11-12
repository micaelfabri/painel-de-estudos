"""Testes da F2: visão do painel, próxima ação, horas da semana e linha do tempo."""


def test_overview_on_2026_11_10(seeded):
    data = seeded.get("/api/overview", params={"today": "2026-11-10"}).json()
    assert data["semester"]["code"] == "2026.3"
    assert len(data["subjects"]) == 5

    # Prova mais próxima: Engenharia de Requisitos em 17/11 às 17h
    first = data["upcoming_exams"][0]
    assert first["subject_name"] == "Engenharia de Requisitos" and first["days_left"] == 7

    # Próxima ação: prova mais próxima com menor progresso -> Engenharia de Requisitos, Tema 1
    action = data["next_action"]
    assert action["subject_name"] == "Engenharia de Requisitos"
    assert action["steps"][0] == "Concluir Tema 1 e Tema 2"
    assert action["after"]["subject_name"] == "Desenvolvimento Web"

    # Linha do tempo: 14 dias, provas em 17/11 e 18/11, prazo de agendamento em 22/11
    days = {d["date"]: d["items"] for d in data["timeline"]}
    assert len(days) == 14
    assert {i["category"] for i in days["2026-11-17"]} == {"exam"}
    assert len(days["2026-11-18"]) == 2
    assert days["2026-11-22"][0]["category"] == "deadline"


def test_software_seguro_action_mentions_lab_and_scheduling(seeded):
    # Depois das provas de 17 e 18/11, sobra Segurança de Software (agendar até 22/11)
    action = seeded.get("/api/overview", params={"today": "2026-11-19"}).json()["next_action"]
    assert action["subject_name"] == "Segurança de Software"
    assert action["steps"] == ["Concluir Tema 4 e Tema 5", "fazer o laboratório", "agendar a prova"]


def test_week_hours_counts_sessions(seeded):
    seeded.post("/api/study-sessions", json={"started_at": "2026-11-10T08:00:00", "seconds": 5400})
    seeded.post("/api/study-sessions", json={"started_at": "2026-11-11T08:00:00", "seconds": 1800})
    seeded.post("/api/study-sessions", json={"started_at": "2026-11-03T08:00:00", "seconds": 999})  # semana anterior
    week = seeded.get("/api/overview", params={"today": "2026-11-12"}).json()["week"]
    assert week["start"] == "2026-11-09"
    assert week["total_seconds"] == 7200
    assert [d["seconds"] for d in week["days"]][:3] == [0, 5400, 1800]


def test_overview_without_semester(client):
    data = client.get("/api/overview").json()
    assert data["semester"] is None and data["subjects"] == [] and data["next_action"] is None
