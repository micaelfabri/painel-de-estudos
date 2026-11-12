"""Visão do painel (modo Estudo): tudo o que a tela inicial precisa numa chamada."""

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import learning, models, settings_store
from .db import get_session

router = APIRouter(prefix="/api", tags=["painel"])


def _counter(done, total):
    return None if total is None else [done or 0, total]


def _exam_info(subject: models.Subject, today: date):
    """Próxima prova da disciplina: com data marcada a partir de hoje, ou a agendar."""
    upcoming = []
    for exam in subject.exams:
        if exam.scheduled_at and exam.scheduled_at.date() >= today:
            upcoming.append((exam.scheduled_at.date(), exam))
        elif exam.scheduled_at is None and exam.schedule_by and exam.schedule_by >= today:
            upcoming.append((exam.schedule_by, exam))
    if not upcoming:
        return None
    key_date, exam = min(upcoming, key=lambda x: x[0])
    return {
        "id": exam.id,
        "kind": exam.kind,
        "scheduled_at": exam.scheduled_at.isoformat() if exam.scheduled_at else None,
        "schedule_by": exam.schedule_by.isoformat() if exam.schedule_by else None,
        "location": exam.location,
        "date": key_date.isoformat(),
        "days_left": (key_date - today).days,
    }


def _subject_payload(subject: models.Subject, today: date) -> dict:
    pp = subject.portal_progress
    lab_pending = bool(
        subject.exam_requires_lab and pp and pp.lab_total and (pp.lab_done or 0) < pp.lab_total
    )
    return {
        "id": subject.id,
        "name": subject.name,
        "hours": subject.hours,
        "percent": pp.percent if pp else None,
        "counters": {
            "contents": _counter(pp.contents_done, pp.contents_total) if pp else None,
            "exercises": _counter(pp.exercises_done, pp.exercises_total) if pp else None,
            "mocks": _counter(pp.mocks_done, pp.mocks_total) if pp else None,
            "lab": _counter(pp.lab_done, pp.lab_total) if pp else None,
        },
        "progress_as_of": pp.as_of.isoformat() if pp and pp.as_of else None,
        "exam": _exam_info(subject, today),
        "exam_requires_lab": subject.exam_requires_lab,
        "lab_pending": lab_pending,
        "pending_topics": [{"id": t.id, "title": t.title} for t in subject.topics if not t.portal_done],
    }


def _join_pt(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " e " + items[-1]


def next_action(subjects: list[dict]) -> dict | None:
    """Regra da próxima ação (SPEC §6.1): prova mais próxima, depois menor progresso.

    Os retestes vencidos entram na frente (ver _with_reviews).
    """
    candidates = [s for s in subjects if s["exam"] and (s["pending_topics"] or s["lab_pending"])]
    if not candidates:
        return None
    # Prova mais próxima (data e hora; "agendar até" conta como fim do dia), depois menor progresso
    candidates.sort(
        key=lambda s: (
            s["exam"]["scheduled_at"] or s["exam"]["date"] + "T23:59",
            s["percent"] if s["percent"] is not None else 0,
        )
    )
    first = candidates[0]

    steps = []
    topics = first["pending_topics"]
    if topics:
        names = [t["title"] for t in topics[:2]]
        steps.append(("Estudar " if len(topics) == 1 else "Concluir ") + _join_pt(names))
    if first["lab_pending"]:
        steps.append("fazer o laboratório")
    if first["exam"]["scheduled_at"] is None:
        steps.append("agendar a prova")

    after = None
    if len(candidates) > 1:
        nxt = candidates[1]
        after = {"subject_id": nxt["id"], "subject_name": nxt["name"], "exam_date": nxt["exam"]["date"]}

    return {
        "kind": "study",
        "subject_id": first["id"],
        "subject_name": first["name"],
        "topic_id": topics[0]["id"] if topics else None,
        "steps": steps,
        "exam_date": first["exam"]["date"],
        "exam_days_left": first["exam"]["days_left"],
        "exam_scheduled": first["exam"]["scheduled_at"] is not None,
        "percent": first["percent"],
        "after": after,
    }


def week_hours(session: Session, today: date) -> dict:
    start = today - timedelta(days=today.weekday())  # segunda-feira
    end = start + timedelta(days=7)
    rows = session.scalars(
        select(models.StudySession).where(
            models.StudySession.started_at >= datetime.combine(start, time.min),
            models.StudySession.started_at < datetime.combine(end, time.min),
        )
    ).all()
    per_day = {start + timedelta(days=i): 0 for i in range(7)}
    for row in rows:
        per_day[row.started_at.date()] += row.seconds
    return {
        "start": start.isoformat(),
        "days": [{"date": d.isoformat(), "seconds": s} for d, s in per_day.items()],
        "total_seconds": sum(per_day.values()),
        "goal_hours": settings_store.get(session, "weekly_hours_goal"),
    }


def timeline(session: Session, subjects: list[models.Subject], today: date, days: int = 14) -> list[dict]:
    end = today + timedelta(days=days)
    buckets: dict[date, list[dict]] = {today + timedelta(days=i): [] for i in range(days)}

    for subject in subjects:
        for exam in subject.exams:
            if exam.scheduled_at and today <= exam.scheduled_at.date() < end:
                buckets[exam.scheduled_at.date()].append(
                    {"category": "exam", "title": f"Prova de {subject.name}", "time": exam.scheduled_at.strftime("%H:%M")}
                )
            elif exam.scheduled_at is None and exam.schedule_by and today <= exam.schedule_by < end:
                buckets[exam.schedule_by].append(
                    {"category": "deadline", "title": f"Limite para agendar a prova de {subject.name}", "time": None}
                )

    deadlines = session.scalars(
        select(models.Deadline).where(models.Deadline.due_date >= today, models.Deadline.due_date < end)
    ).all()
    for d in deadlines:
        buckets[d.due_date].append(
            {"category": "event" if d.kind == "event" else "deadline", "title": d.title, "time": None}
        )

    return [{"date": d.isoformat(), "items": items} for d, items in buckets.items()]


@router.get("/overview")
def overview(today: date | None = Query(None, description="Só para testes; padrão = hoje"),
             session: Session = Depends(get_session)):
    return compute_overview(session, today or date.today())


def compute_overview(session: Session, today: date) -> dict:
    semester = session.scalars(
        select(models.Semester).where(models.Semester.is_current.is_(True)).options(selectinload(models.Semester.degree))
    ).first()

    subjects: list[models.Subject] = []
    if semester:
        subjects = list(
            session.scalars(
                select(models.Subject)
                .where(models.Subject.semester_id == semester.id)
                .options(
                    selectinload(models.Subject.portal_progress),
                    selectinload(models.Subject.exams),
                    selectinload(models.Subject.topics),
                )
                .order_by(models.Subject.name)
            ).all()
        )

    payload = [_subject_payload(s, today) for s in subjects]
    study = next_action(payload)
    exams = sorted(
        ({"subject_id": s["id"], "subject_name": s["name"], **s["exam"]} for s in payload if s["exam"]),
        key=lambda e: (e["date"], e["scheduled_at"] or "9"),
    )

    return {
        "today": today.isoformat(),
        "semester": {"id": semester.id, "code": semester.code, "degree_name": semester.degree.name} if semester else None,
        "subjects": payload,
        "upcoming_exams": exams,
        "next_action": _with_reviews(session, today, study),
        "next_study_action": study,
        "week": week_hours(session, today),
        "timeline": timeline(session, subjects, today),
        "timer": {
            "goal_minutes": settings_store.get(session, "timer_goal_minutes"),
            "alarm_minutes": settings_store.get(session, "timer_alarm_minutes"),
        },
    }


def _with_reviews(session: Session, today: date, study_action: dict | None) -> dict | None:
    """Retestes vencidos passam na frente do estudo novo (SPEC §6.1)."""
    due = learning.due_reviews(session, today)
    if not due:
        return study_action
    r = due[0]
    topic = session.get(models.Topic, r.topic_id)
    subject = session.get(models.Subject, topic.subject_id)
    return {
        "kind": "review",
        "review_id": r.id,
        "subject_id": subject.id,
        "subject_name": subject.name,
        "topic_id": topic.id,
        "steps": [f"Fazer o {learning.LABELS[r.attempt_type]} de {topic.title}"],
        "due_date": r.due_date.isoformat(),
        "reviews_due": len(due),
        "after": study_action and {"subject_id": study_action["subject_id"], "subject_name": study_action["subject_name"],
                                   "exam_date": study_action["exam_date"]},
    }
