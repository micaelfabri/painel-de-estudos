"""Medição de aprendizado (SPEC §6.3): retestes em 1, 7 e 21 dias e status do tema.

- Primeiro conjunto concluído de um tema → agenda retestes de 1, 7 e 21 dias.
- Reteste de 7 dias (ou de 3 dias, depois de um "revisar") decide o status:
  nota ≥ limiar (padrão 70%) → "aprendido"; abaixo → "revisar" + novo reteste em 3 dias.
- Retestes de 1 e 21 dias ficam registrados, mas não mudam o status (o SPEC não define isso).
"""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import models, settings_store
from .db import get_session

RETEST_DAYS = {"retest_1d": 1, "retest_7d": 7, "retest_21d": 21}
DECISIVE = {"retest_7d", "retest_3d"}

LABELS = {
    "first": "primeira vez",
    "retest_1d": "reteste de 1 dia",
    "retest_7d": "reteste de 7 dias",
    "retest_21d": "reteste de 21 dias",
    "retest_3d": "reteste de revisão (3 dias)",
}


def on_set_completed(session: Session, qs: models.QuestionSet) -> None:
    """Chamado quando um conjunto fecha (todas as questões válidas respondidas)."""
    topic = session.get(models.Topic, qs.topic_id)
    done_day = (qs.completed_at or datetime.now()).date()

    # Fecha o reteste agendado correspondente (o mais antigo em aberto do mesmo tipo)
    pending = session.scalars(
        select(models.ReviewSchedule)
        .where(models.ReviewSchedule.topic_id == qs.topic_id,
               models.ReviewSchedule.attempt_type == qs.attempt_type,
               models.ReviewSchedule.done.is_(False))
        .order_by(models.ReviewSchedule.due_date)
    ).first()
    if pending:
        pending.done = True
        pending.question_set_id = qs.id

    if qs.attempt_type == "first":
        already = session.scalars(
            select(models.ReviewSchedule).where(models.ReviewSchedule.topic_id == qs.topic_id)
        ).first()
        if not already:
            for kind, days in RETEST_DAYS.items():
                session.add(models.ReviewSchedule(topic_id=qs.topic_id, attempt_type=kind,
                                                  due_date=done_day + timedelta(days=days)))
        if topic.learning_status != "learned":
            topic.learning_status = "pending"

    elif qs.attempt_type in DECISIVE and qs.score is not None:
        threshold = float(settings_store.get(session, "learned_threshold"))
        if qs.score >= threshold:
            topic.learning_status = "learned"
        else:
            topic.learning_status = "review"
            session.add(models.ReviewSchedule(topic_id=qs.topic_id, attempt_type="retest_3d",
                                              due_date=done_day + timedelta(days=3)))


def due_reviews(session: Session, today: date) -> list[models.ReviewSchedule]:
    return list(
        session.scalars(
            select(models.ReviewSchedule)
            .where(models.ReviewSchedule.done.is_(False), models.ReviewSchedule.due_date <= today)
            .order_by(models.ReviewSchedule.due_date)
        ).all()
    )


router = APIRouter(prefix="/api/learning", tags=["aprendizado"])


def _review_out(session: Session, r: models.ReviewSchedule) -> dict:
    topic = session.get(models.Topic, r.topic_id)
    subject = session.get(models.Subject, topic.subject_id)
    return {
        "id": r.id, "topic_id": r.topic_id, "topic_title": topic.title, "subject_id": subject.id,
        "subject_name": subject.name, "attempt_type": r.attempt_type, "label": LABELS[r.attempt_type],
        "due_date": r.due_date.isoformat(), "has_text": bool(topic.source_text),
    }


@router.get("/reviews")
def list_reviews(today: date | None = Query(None), include_future: bool = False,
                 session: Session = Depends(get_session)):
    today = today or date.today()
    stmt = select(models.ReviewSchedule).where(models.ReviewSchedule.done.is_(False))
    if not include_future:
        stmt = stmt.where(models.ReviewSchedule.due_date <= today)
    rows = session.scalars(stmt.order_by(models.ReviewSchedule.due_date)).all()
    return [_review_out(session, r) for r in rows]


@router.get("/topics")
def topic_scores(subject_id: int | None = None, session: Session = Depends(get_session)):
    """Acerto por tema: primeira nota, último reteste e status."""
    stmt = (select(models.Topic).options(selectinload(models.Topic.subject))
            .order_by(models.Topic.subject_id, models.Topic.position))
    if subject_id is not None:
        stmt = stmt.where(models.Topic.subject_id == subject_id)
    out = []
    for topic in session.scalars(stmt).all():
        sets = session.scalars(
            select(models.QuestionSet)
            .where(models.QuestionSet.topic_id == topic.id, models.QuestionSet.completed_at.is_not(None))
            .order_by(models.QuestionSet.completed_at)
        ).all()
        if not sets:
            continue
        first = next((s for s in sets if s.attempt_type == "first"), None)
        decisive = [s for s in sets if s.attempt_type in DECISIVE]
        next_review = session.scalars(
            select(models.ReviewSchedule)
            .where(models.ReviewSchedule.topic_id == topic.id, models.ReviewSchedule.done.is_(False))
            .order_by(models.ReviewSchedule.due_date)
        ).first()
        out.append({
            "topic_id": topic.id, "topic_title": topic.title, "subject_id": topic.subject_id,
            "subject_name": topic.subject.name, "status": topic.learning_status,
            "first_score": first.score if first else None,
            "decisive_score": decisive[-1].score if decisive else None,
            "last_score": sets[-1].score, "last_attempt": LABELS[sets[-1].attempt_type],
            "attempts": len(sets),
            "next_review": ({"date": next_review.due_date.isoformat(), "label": LABELS[next_review.attempt_type]}
                            if next_review else None),
        })
    return out


# --- Revisar erros -----------------------------------------------------------


@router.get("/mistakes")
def mistakes_to_review(include_reviewed: bool = False, subject_id: int | None = None,
                       session: Session = Depends(get_session)):
    stmt = select(models.Mistake).order_by(models.Mistake.created_at.desc())
    if not include_reviewed:
        stmt = stmt.where(models.Mistake.reviewed.is_(False))
    out = []
    for m in session.scalars(stmt).all():
        q = session.get(models.Question, m.question_id)
        topic = session.get(models.Topic, m.topic_id)
        if subject_id is not None and topic.subject_id != subject_id:
            continue
        subject = session.get(models.Subject, topic.subject_id)
        out.append({
            "id": m.id, "topic_id": topic.id, "topic_title": topic.title, "subject_name": subject.name,
            "statement": q.statement, "options": q.options, "correct_index": q.correct_index,
            "chosen_index": q.answer.chosen_index if q.answer else None, "explanation": q.explanation,
            "video_minute": m.video_minute, "reviewed": m.reviewed,
        })
    return out


# --- Checklist do dia (exceção E11 do DS: marcar conclui na hora) -------------


class ChecklistIn(BaseModel):
    day: date
    label: str = Field(min_length=1, max_length=300)
    planned_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    topic_id: int | None = None
    review_id: int | None = None
    done: bool = False
    position: int = 0


def _item_out(i: models.ChecklistItem) -> dict:
    return {"id": i.id, "day": i.day.isoformat(), "label": i.label, "planned_minutes": i.planned_minutes,
            "topic_id": i.topic_id, "review_id": i.review_id, "done": i.done, "position": i.position}


@router.get("/checklist")
def get_checklist(day: date | None = Query(None), session: Session = Depends(get_session)):
    day = day or date.today()
    rows = session.scalars(
        select(models.ChecklistItem).where(models.ChecklistItem.day == day)
        .order_by(models.ChecklistItem.position, models.ChecklistItem.id)
    ).all()
    return [_item_out(r) for r in rows]


@router.post("/checklist", status_code=201)
def add_checklist_item(data: ChecklistIn, session: Session = Depends(get_session)):
    item = models.ChecklistItem(**data.model_dump())
    session.add(item)
    session.commit()
    return _item_out(item)


class ChecklistPatch(BaseModel):
    done: bool | None = None
    label: str | None = Field(default=None, min_length=1, max_length=300)


@router.patch("/checklist/{item_id}")
def patch_checklist_item(item_id: int, data: ChecklistPatch, session: Session = Depends(get_session)):
    item = session.get(models.ChecklistItem, item_id)
    if item is None:
        raise HTTPException(404, "item não encontrado")
    for key, value in data.model_dump(exclude_none=True).items():
        setattr(item, key, value)
    session.commit()
    return _item_out(item)


@router.delete("/checklist/{item_id}", status_code=204)
def delete_checklist_item(item_id: int, session: Session = Depends(get_session)):
    item = session.get(models.ChecklistItem, item_id)
    if item is None:
        raise HTTPException(404, "item não encontrado")
    session.delete(item)
    session.commit()


@router.post("/checklist/plan")
def plan_day(day: date | None = Query(None), session: Session = Depends(get_session)):
    """Monta o dia: retestes vencidos + a próxima ação sugerida. Não duplica o que já está na lista."""
    from .overview import compute_overview  # import local: overview depende deste módulo

    day = day or date.today()
    existing = session.scalars(select(models.ChecklistItem).where(models.ChecklistItem.day == day)).all()
    have_reviews = {i.review_id for i in existing if i.review_id}
    have_labels = {i.label for i in existing}
    position = max((i.position for i in existing), default=0)
    added = 0

    for r in due_reviews(session, day):
        if r.id in have_reviews:
            continue
        info = _review_out(session, r)
        position += 1
        session.add(models.ChecklistItem(day=day, label=f"{info['label'].capitalize()}: {info['topic_title']} · {info['subject_name']}",
                                         topic_id=r.topic_id, review_id=r.id, position=position))
        added += 1

    action = compute_overview(session, day)["next_study_action"]
    goal = int(settings_store.get(session, "timer_goal_minutes"))
    if action and action.get("kind") == "study":
        for step in action["steps"]:
            label = f"{step[0].upper()}{step[1:]} · {action['subject_name']}"
            if label in have_labels:
                continue
            position += 1
            is_topic = step.startswith(("Estudar", "Concluir"))
            session.add(models.ChecklistItem(day=day, label=label, position=position,
                                             planned_minutes=goal if is_topic else None,
                                             topic_id=action["topic_id"] if is_topic else None))
            added += 1
    session.commit()
    return {"added": added, "items": get_checklist(day, session)}
