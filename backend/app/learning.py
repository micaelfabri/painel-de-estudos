"""Medição de aprendizado (SPEC §6.3): retestes em 1, 7 e 21 dias e status do tema.

- Primeiro conjunto concluído de um tema → agenda retestes de 1, 7 e 21 dias.
- Reteste de 7 dias (ou de 3 dias, depois de um "revisar") decide o status:
  nota ≥ limiar (padrão 70%) → "aprendido"; abaixo → "revisar" + novo reteste em 3 dias.
- v1.5 (D29, regra "a"): reteste de 21 dias abaixo do limiar manda o tema de volta para "revisar"
  (+ reteste em 3 dias); acima, não muda nada. O reteste de 1 dia só fica registrado.
- Refazer erradas, testes de foco e simulado não mudam o status do tema.

Ciclo dos erros (v1.5, D28): open (não revisado) → reviewed (revisado, falta acertar) →
fixed (acertou num refazer) ou again (errou de novo, revisar de novo).
"""

from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import areas, models, settings_store
from .db import get_session

RETEST_DAYS = {"retest_1d": 1, "retest_7d": 7, "retest_21d": 21}
DECISIVE = {"retest_7d", "retest_3d"}
# v1.5 (D29): o reteste de 21 dias só pode tirar o "aprendido" (nota abaixo do limiar)
DEMOTES = {"retest_21d"}

# Ciclo dos erros (D28)
MISTAKE_STATUSES = ("open", "reviewed", "again", "fixed")
MISTAKE_LABELS = {"open": "não revisado", "reviewed": "revisado, falta acertar", "again": "revisar de novo",
                  "fixed": "corrigido"}
# Erros que ainda pedem atenção (tudo menos "corrigido")
UNFIXED = ("open", "reviewed", "again")

LABELS = {
    "first": "primeira vez",
    "retest_1d": "reteste de 1 dia",
    "retest_7d": "reteste de 7 dias",
    "retest_21d": "reteste de 21 dias",
    "retest_3d": "reteste de revisão (3 dias)",
    # v1.3 (D15, D16): fora do ciclo de retestes
    "redo": "refazer erradas",
    "focus_errors": "novo teste (erros)",
    "focus_hits": "novo teste (acertos)",
    "simulation": "simulado da prova",
}
# Tipos que contam para o ciclo do tema (primeira vez + retestes)
CYCLE = {"first", *RETEST_DAYS, "retest_3d"}


def on_set_completed(session: Session, qs: models.QuestionSet) -> None:
    """Chamado quando um conjunto fecha (todas as questões válidas respondidas)."""
    if qs.attempt_type not in CYCLE or qs.topic_id is None:
        return  # refazer, testes de foco e simulado ficam só no histórico
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

    elif qs.attempt_type in DEMOTES and qs.score is not None:
        threshold = float(settings_store.get(session, "learned_threshold"))
        if qs.score < threshold:
            topic.learning_status = "review"
            session.add(models.ReviewSchedule(topic_id=qs.topic_id, attempt_type="retest_3d",
                                              due_date=done_day + timedelta(days=3)))


def record_retry(session: Session, question: models.Question, correct: bool, topic_id: int | None) -> None:
    """Resposta numa cópia do "refazer erradas" (D28): atualiza o erro da questão original.

    Não cria um erro novo na cópia: acertou → "fixed"; errou → "again".
    """
    root_id = question.source_question_id
    mistake = session.scalars(select(models.Mistake).where(models.Mistake.question_id == root_id)).first()
    if mistake is None:
        if correct or topic_id is None:
            return
        mistake = models.Mistake(question_id=root_id, topic_id=topic_id)
        session.add(mistake)
    mistake.status = "fixed" if correct else "again"
    mistake.reviewed = True


def mistake_counts(session: Session, *, topic_id: int | None = None, subject_id: int | None = None,
                   area: areas.Area | None = None) -> dict:
    """Erros por status (D28) de um tema, de uma disciplina ou de uma área (v1.8)."""
    stmt = select(models.Mistake.status, models.Mistake.topic_id)
    if topic_id is not None:
        stmt = stmt.where(models.Mistake.topic_id == topic_id)
    if subject_id is not None:
        stmt = stmt.join(models.Topic, models.Topic.id == models.Mistake.topic_id).where(
            models.Topic.subject_id == subject_id)
    counts = dict.fromkeys(MISTAKE_STATUSES, 0)
    course_ids = areas.course_subject_ids(session) if area else set()
    topic_subject = areas.topic_subjects(session) if area else {}
    for status, tid in session.execute(stmt).all():
        if area and not areas.in_area(topic_subject.get(tid), area, course_ids):
            continue
        counts[status if status in counts else "open"] += 1
    return counts


def due_reviews(session: Session, today: date, area: areas.Area | None = None) -> list[models.ReviewSchedule]:
    rows = list(
        session.scalars(
            select(models.ReviewSchedule)
            .where(models.ReviewSchedule.done.is_(False), models.ReviewSchedule.due_date <= today)
            .order_by(models.ReviewSchedule.due_date)
        ).all()
    )
    if area is None:
        return rows
    course_ids = areas.course_subject_ids(session)
    topic_subject = areas.topic_subjects(session)
    return [r for r in rows if areas.in_area(topic_subject.get(r.topic_id), area, course_ids)]


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
        cycle = [s for s in sets if s.attempt_type in CYCLE]
        if not cycle:
            continue
        first = next((s for s in cycle if s.attempt_type == "first"), None)
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
            "last_score": cycle[-1].score, "last_attempt": LABELS.get(cycle[-1].attempt_type, cycle[-1].attempt_type),
            "attempts": len(cycle),
            "next_review": ({"date": next_review.due_date.isoformat(), "label": LABELS[next_review.attempt_type]}
                            if next_review else None),
        })
    return out


# --- Revisar erros -----------------------------------------------------------


@router.get("/mistakes")
def mistakes_to_review(status: str | None = Query(None, description="open,reviewed,again,fixed; padrão = sem os corrigidos"),
                       include_reviewed: bool = False, subject_id: int | None = None, topic_id: int | None = None,
                       area: areas.Area | None = None, session: Session = Depends(get_session)):
    """Erros para revisar (D28). Padrão: todos menos os corrigidos; `include_reviewed` = todos."""
    wanted = [x for x in (status or "").split(",") if x in MISTAKE_STATUSES]
    if not wanted:
        wanted = list(MISTAKE_STATUSES) if include_reviewed else list(UNFIXED)
    stmt = (select(models.Mistake).where(models.Mistake.status.in_(wanted))
            .order_by(models.Mistake.updated_at.desc(), models.Mistake.id.desc()))
    if topic_id is not None:
        stmt = stmt.where(models.Mistake.topic_id == topic_id)
    out = []
    course_ids = areas.course_subject_ids(session)
    for m in session.scalars(stmt).all():
        q = session.get(models.Question, m.question_id)
        topic = session.get(models.Topic, m.topic_id)
        if subject_id is not None and topic.subject_id != subject_id:
            continue
        if not areas.in_area(topic.subject_id, area, course_ids):
            continue
        subject = session.get(models.Subject, topic.subject_id)
        out.append({
            "id": m.id, "topic_id": topic.id, "topic_title": topic.title, "subject_name": subject.name,
            "statement": q.statement, "options": q.options, "correct_index": q.correct_index,
            "chosen_index": q.answer.chosen_index if q.answer else None, "explanation": q.explanation,
            "video_minute": m.video_minute, "reviewed": m.reviewed, "status": m.status,
            "status_label": MISTAKE_LABELS.get(m.status, m.status), "subject_id": subject.id,
        })
    return out


@router.get("/mistakes/summary")
def mistakes_summary(subject_id: int | None = None, area: areas.Area | None = None,
                     session: Session = Depends(get_session)):
    return mistake_counts(session, subject_id=subject_id, area=area)


class MistakeStatusIn(BaseModel):
    # Só "revisado" é manual; corrigido e revisar de novo vêm das respostas no refazer
    status: Literal["open", "reviewed"]


@router.patch("/mistakes/{mistake_id}")
def set_mistake_status(mistake_id: int, data: MistakeStatusIn, session: Session = Depends(get_session)):
    m = session.get(models.Mistake, mistake_id)
    if m is None:
        raise HTTPException(404, "erro não encontrado")
    m.status = data.status
    m.reviewed = data.status != "open"
    session.commit()
    return {"id": m.id, "status": m.status, "status_label": MISTAKE_LABELS[m.status]}


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


# v1.7.2: tarefas não feitas de dias anteriores podem ser trazidas para hoje. O item do dia antigo fica como
# estava (o detalhe do dia no Desempenho mostra "não feita"); hoje ganha uma cópia.
CARRY_DAYS = 14


def _pending_from_past(session: Session, day: date) -> list[models.ChecklistItem]:
    """Não feitas dos últimos 14 dias, a mais recente de cada nome, sem o que já está no dia.

    Ficam de fora os retestes (voltam pelo "Montar o dia" enquanto estiverem vencidos) e o item automático
    de cards vencidos (a contagem muda todo dia).
    """
    today_labels = set(session.scalars(select(models.ChecklistItem.label)
                                       .where(models.ChecklistItem.day == day)).all())
    rows = session.scalars(
        select(models.ChecklistItem)
        .where(models.ChecklistItem.day < day, models.ChecklistItem.day >= day - timedelta(days=CARRY_DAYS),
               models.ChecklistItem.done.is_(False), models.ChecklistItem.review_id.is_(None))
        .order_by(models.ChecklistItem.day.desc(), models.ChecklistItem.position, models.ChecklistItem.id)
    ).all()
    seen: set[str] = set()
    out = []
    for r in rows:
        if r.label in today_labels or r.label in seen or r.label.startswith("Revisar cards vencidos"):
            continue
        seen.add(r.label)
        out.append(r)
    return out


@router.get("/checklist/pending")
def get_pending(day: date | None = Query(None), session: Session = Depends(get_session)):
    return [_item_out(r) for r in _pending_from_past(session, day or date.today())]


@router.post("/checklist/carry")
def carry_pending(day: date | None = Query(None), session: Session = Depends(get_session)):
    """Traz para o dia as não feitas de dias anteriores (cópia; o dia antigo fica como estava)."""
    day = day or date.today()
    pending = _pending_from_past(session, day)
    position = max(session.scalars(select(models.ChecklistItem.position)
                                   .where(models.ChecklistItem.day == day)).all(), default=0)
    for r in pending:
        position += 1
        session.add(models.ChecklistItem(day=day, label=r.label, planned_minutes=r.planned_minutes,
                                         topic_id=r.topic_id, position=position))
    session.commit()
    return {"added": len(pending), "items": get_checklist(day, session)}


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

    # D40: os cursos só entram no plano do dia com a chave ligada em Configurações
    with_courses = bool(settings_store.get(session, "courses_in_day_plan"))
    for r in due_reviews(session, day, area=None if with_courses else "faculdade"):
        if r.id in have_reviews:
            continue
        info = _review_out(session, r)
        position += 1
        session.add(models.ChecklistItem(day=day, label=f"{info['label'].capitalize()}: {info['topic_title']} · {info['subject_name']}",
                                         topic_id=r.topic_id, review_id=r.id, position=position))
        added += 1

    # v1.6 (D35): cards vencidos viram um item do dia (um só, com a contagem)
    from . import cards  # import local: cards depende deste módulo

    due_cards = cards.due_count(session, day)
    if due_cards and not any(lbl.startswith("Revisar cards") for lbl in have_labels):
        position += 1
        session.add(models.ChecklistItem(day=day, label=f"Revisar cards vencidos ({due_cards})", position=position))
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
    if with_courses:
        added, position = _plan_courses(session, day, have_labels, position, added)
    session.commit()
    return {"added": added, "items": get_checklist(day, session)}


def _plan_courses(session: Session, day: date, have_labels: set[str], position: int, added: int) -> tuple[int, int]:
    """D40 ligado: a próxima aula de cada curso em andamento vira uma tarefa do dia."""
    from .courses import _courses, _modules, next_lesson  # import local: courses depende deste módulo

    for c in _courses(session):
        if (c.course_status or "doing") != "doing":
            continue
        nxt = next_lesson(_modules(session, c.id))
        if not nxt:
            continue
        label = (f"Próxima aula: {nxt['title']} · {c.name}" if nxt["title"]
                 else f"Continuar o {nxt['module']} · {c.name}")
        if label in have_labels:
            continue
        position += 1
        session.add(models.ChecklistItem(day=day, label=label, position=position, topic_id=nxt["topic_id"]))
        added += 1
    return added, position
