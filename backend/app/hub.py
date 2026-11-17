"""Resumo para o hub pessoal (SPEC D45): só leitura, sem notas, reaproveitando o cálculo da tela inicial."""

import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import areas, models, overview
from .db import get_session

log = logging.getLogger("painel.hub")

router = APIRouter(prefix="/api", tags=["hub"])

DEADLINE_DAYS = 30  # provas e prazos dos próximos 30 dias
EXAM_ALERT_DAYS = 7  # prova perto o bastante para virar alerta
MAX_ALERTS = 5


def _hours(seconds: int) -> str:
    h, m = divmod(seconds // 60, 60)
    return f"{h}h{m:02d}" if m else f"{h}h"


def _next_step(action: dict | None) -> str:
    """Mesma próxima ação da tela inicial, em uma frase (reteste vencido primeiro, depois estudo)."""
    if not action:
        return ""
    steps = action.get("steps") or []
    text = "; ".join(steps) if action.get("kind") == "review" else ", ".join(steps)
    name = action.get("subject_name")
    return f"{text} ({name})" if text and name else text


def _deadlines(view: dict) -> list[dict]:
    """Provas e prazos ainda não feitos da faixa do Painel, estendida para 30 dias."""
    out = []
    for day in view["timeline"]:
        for item in day["items"]:
            if item.get("done"):
                continue
            title = item["title"] + (f" {item['time']}" if item.get("time") else "")
            out.append({"date": day["date"], "title": title})
    return out


def _overdue(session: Session, today: date) -> list[models.Deadline]:
    """Prazos da faculdade que passaram sem ser marcados como feitos."""
    course_ids = areas.course_subject_ids(session)
    rows = session.scalars(
        select(models.Deadline)
        .where(models.Deadline.due_date < today, models.Deadline.done_at.is_(None))
        .order_by(models.Deadline.due_date)
    ).all()
    return [d for d in rows if areas.in_area(d.subject_id, "faculdade", course_ids)]


def build_summary(session: Session, today: date) -> dict:
    view = overview.compute_overview(session, today)
    # a faixa do Painel é de 14 dias; o hub pede 30 (mesma função, só a janela muda)
    view["timeline"] = overview.timeline(session, _current_subjects(session), today, days=DEADLINE_DAYS)

    week = view["week"]
    pending = sum(len(s["pending_topics"]) for s in view["subjects"])
    action = view["next_action"] or {}
    reviews = action.get("reviews_due", 0) if action.get("kind") == "review" else 0
    parts = [f"{_hours(week['total_seconds'])} estudadas na semana"
             + (f" (meta {week['goal_hours']}h)" if week.get("goal_hours") else "")]
    if view["subjects"]:
        parts.append(f"{pending} tema(s) pendente(s)")
    if reviews:
        parts.append(f"{reviews} reteste(s) vencido(s)")
    state = " · ".join(parts) if view["semester"] else ""

    alerts: list[str] = []
    if reviews:
        alerts.append(f"{reviews} reteste(s) vencido(s)")
    if view["cards_due"]:
        alerts.append(f"{view['cards_due']} card(s) para revisar hoje")
    for exam in view["upcoming_exams"]:
        days = exam.get("days_left")
        if days is not None and days <= EXAM_ALERT_DAYS:
            when = "hoje" if days == 0 else "amanhã" if days == 1 else f"em {days} dias"
            what = "Prova" if exam.get("scheduled_at") else "Agendar a prova"
            alerts.append(f"{what} de {exam['subject_name']} {when}")
    late = _overdue(session, today)
    if late:
        alerts.append(f"{len(late)} prazo(s) passado(s) sem marcar como feito")

    return {
        "source": "painel",
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "state": state,
        "next_step": _next_step(view["next_action"]),
        "deadlines": _deadlines(view),
        "alerts": alerts[:MAX_ALERTS],
    }


def _current_subjects(session: Session) -> list[models.Subject]:
    semester = session.scalars(select(models.Semester).where(models.Semester.is_current.is_(True))).first()
    if not semester:
        return []
    return list(session.scalars(select(models.Subject).where(models.Subject.semester_id == semester.id)).all())


@router.get("/hub-summary")
def hub_summary(today: date | None = Query(None, description="Só para testes; padrão = hoje"),
                session: Session = Depends(get_session)):
    # Nunca erro para o hub: se algo falhar, devolve o formato com campos vazios
    try:
        return build_summary(session, today or date.today())
    except Exception:  # noqa: BLE001 — o hub só precisa saber que não há dados
        log.exception("Resumo para o hub falhou")
        return {"source": "painel", "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "state": "", "next_step": "", "deadlines": [], "alerts": []}
