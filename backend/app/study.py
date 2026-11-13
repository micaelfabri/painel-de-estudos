"""Lado Estudo da v1.3 (SPEC D14, D15, D20): provas e prazos, histórico, resumo da semana e backup.

- Provas e prazos: uma lista só, com marcar como feito (a edição completa usa as rotas de cadastro).
- Histórico: todo conjunto de questões continua salvo e visível, com a evolução por tema.
- Resumo da semana e backup diário do banco (guarda os últimos 14).
"""

import os
import sqlite3
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import areas, learning, models
from .db import get_session

router = APIRouter(prefix="/api/study", tags=["estudo"])

KIND_LABELS = {"deadline": "Prazo", "event": "Evento", "lab": "Laboratório", "activity": "Atividade",
               "mock": "Simulado"}


# --- Provas e prazos ---------------------------------------------------------


def _exam_out(e: models.Exam) -> dict:
    when = e.scheduled_at.date() if e.scheduled_at else e.schedule_by
    return {
        "type": "exam", "id": e.id, "subject_id": e.subject_id, "subject_name": e.subject.name,
        "title": f"{e.kind} · {e.subject.name}", "kind": e.kind, "kind_label": "Prova",
        "date": when.isoformat() if when else None,
        "time": e.scheduled_at.strftime("%H:%M") if e.scheduled_at else None,
        "to_schedule": e.scheduled_at is None and e.schedule_by is not None,
        "location": e.location, "score": e.score, "done": e.done_at is not None, "notes": e.notes,
        "max_score": exam_max(e.subject),
    }


def exam_max(subject: models.Subject) -> float:
    """Nota máxima da prova pela regra da disciplina (ex.: AV/AVS 0–8 no padrão 2026); sem regra, 10."""
    from . import grading

    try:
        rule = grading.GradingRule.model_validate(subject.grading_rule or {})
    except ValueError:
        return 10.0
    for part in rule.parts:
        if (part.source or grading.DEFAULT_SOURCE.get(part.key)) == "exam":
            return part.max
    return 10.0


def _deadline_out(d: models.Deadline, subjects: dict[int, str]) -> dict:
    return {
        "type": "deadline", "id": d.id, "subject_id": d.subject_id,
        "subject_name": subjects.get(d.subject_id) if d.subject_id else None,
        "title": d.title, "kind": d.kind, "kind_label": KIND_LABELS.get(d.kind, d.kind),
        "date": d.due_date.isoformat(), "time": None, "to_schedule": False, "location": None,
        "score": d.score, "total_questions": d.total_questions, "first_try_correct": d.first_try_correct,
        "wrong_attempts": d.wrong_attempts, "done": d.done_at is not None, "notes": d.notes,
        "notion_page_id": d.notion_page_id, "max_score": SCORE_SCALE.get(d.kind, 10.0),
    }


@router.get("/agenda")
def agenda(session: Session = Depends(get_session)):
    """Provas, prazos, eventos, laboratórios e atividades numa lista só, por data."""
    subjects = {s.id: s.name for s in session.scalars(select(models.Subject)).all()}
    exams = session.scalars(select(models.Exam).options(selectinload(models.Exam.subject))).all()
    deadlines = session.scalars(select(models.Deadline)).all()
    items = [_exam_out(e) for e in exams] + [_deadline_out(d, subjects) for d in deadlines]
    items.sort(key=lambda i: (i["date"] or "9999", i["time"] or "99"))
    return items


class DoneIn(BaseModel):
    done: bool


@router.patch("/exams/{exam_id}/done")
def set_exam_done(exam_id: int, data: DoneIn, session: Session = Depends(get_session)):
    exam = session.get(models.Exam, exam_id)
    if exam is None:
        raise HTTPException(404, "prova não encontrada")
    exam.done_at = (exam.done_at or datetime.now()) if data.done else None
    session.commit()
    return {"id": exam.id, "done": exam.done_at is not None}


@router.patch("/deadlines/{deadline_id}/done")
def set_deadline_done(deadline_id: int, data: DoneIn, session: Session = Depends(get_session)):
    d = session.get(models.Deadline, deadline_id)
    if d is None:
        raise HTTPException(404, "prazo não encontrado")
    d.done_at = (d.done_at or datetime.now()) if data.done else None
    session.commit()
    return {"id": d.id, "done": d.done_at is not None}


class ResultIn(BaseModel):
    """Resultado confirmado (D17): vem da proposta dos prints ou digitado."""

    total_questions: int | None = Field(default=None, ge=1, le=500)
    first_try_correct: int | None = Field(default=None, ge=0, le=500)
    wrong_attempts: int | None = Field(default=None, ge=0, le=5000)
    score: float | None = Field(default=None, ge=0, le=10)
    done: bool = True


# D26: simulado da faculdade vale até 1,0 ponto (certas ÷ questões); o resto é nota de 0 a 10
SCORE_SCALE = {"mock": 1.0}


def _auto_score(kind: str, total: int | None, first: int | None) -> float | None:
    if not total or first is None:
        return None
    scale = SCORE_SCALE.get(kind, 10.0)
    return round(first / total * scale, 2 if scale < 10 else 1)


@router.put("/deadlines/{deadline_id}/result")
def set_deadline_result(deadline_id: int, data: ResultIn, session: Session = Depends(get_session)):
    d = session.get(models.Deadline, deadline_id)
    if d is None:
        raise HTTPException(404, "prazo não encontrado")
    if data.total_questions and data.first_try_correct is not None and data.first_try_correct > data.total_questions:
        raise HTTPException(422, "acertos de primeira maior que o total de questões")
    score = data.score
    if score is None:
        score = _auto_score(d.kind, data.total_questions, data.first_try_correct)
    if score is not None and score > SCORE_SCALE.get(d.kind, 10.0):
        raise HTTPException(422, f"nota acima do máximo ({SCORE_SCALE.get(d.kind, 10.0):g}) para este tipo")
    d.total_questions, d.first_try_correct = data.total_questions, data.first_try_correct
    d.wrong_attempts, d.score = data.wrong_attempts, score
    d.done_at = (d.done_at or datetime.now()) if data.done else None
    session.commit()
    return _deadline_out(d, {s.id: s.name for s in session.scalars(select(models.Subject)).all()})


@router.put("/exams/{exam_id}/result")
def set_exam_result(exam_id: int, data: ResultIn, session: Session = Depends(get_session)):
    exam = session.get(models.Exam, exam_id)
    if exam is None:
        raise HTTPException(404, "prova não encontrada")
    score = data.score
    top = exam_max(exam.subject)
    if score is None and data.total_questions and data.first_try_correct is not None:
        score = round(data.first_try_correct / data.total_questions * top, 1)
    if score is not None and score > top:
        raise HTTPException(422, f"nota acima do máximo da prova ({top:g}) pela regra da disciplina")
    exam.score = score
    exam.done_at = (exam.done_at or datetime.now()) if data.done else None
    session.commit()
    return _exam_out(exam)


class NotionLinkIn(BaseModel):
    notion_page_id: str | None = Field(default=None, max_length=64)


@router.put("/deadlines/{deadline_id}/notion")
def link_deadline_page(deadline_id: int, data: NotionLinkIn, session: Session = Depends(get_session)):
    """Liga a página do Notion do próprio item (ex.: a página do laboratório no caderno)."""
    d = session.get(models.Deadline, deadline_id)
    if d is None:
        raise HTTPException(404, "prazo não encontrado")
    d.notion_page_id = (data.notion_page_id or "").strip() or None
    session.commit()
    return _deadline_out(d, {s.id: s.name for s in session.scalars(select(models.Subject)).all()})


# --- Sessões do cronômetro (D24) --------------------------------------------


class TimerStartIn(BaseModel):
    subject_id: int | None = None
    started_at: datetime


class TimerPatchIn(BaseModel):
    subject_id: int | None = None
    pauses: int | None = Field(default=None, ge=0, le=10_000)
    # Finalizar fecha a sessão com o relógio oculto (início até agora); "reset" = Zerar das sessões antigas
    end_reason: Literal["finished", "reset"] | None = None
    ended_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)


def _timer_out(session: Session, t: models.TimerSession, subjects: dict[int, str] | None = None) -> dict:
    active = sum(session.scalars(select(models.StudySession.seconds)
                                 .where(models.StudySession.timer_session_id == t.id)).all())
    if subjects is None:
        subjects = {s.id: s.name for s in session.scalars(select(models.Subject)).all()}
    return {
        "id": t.id, "subject_id": t.subject_id, "subject_name": subjects.get(t.subject_id) if t.subject_id else None,
        "started_at": t.started_at.isoformat(), "ended_at": t.ended_at.isoformat() if t.ended_at else None,
        "pauses": t.pauses, "active_seconds": active, "wall_seconds": t.wall_seconds,
        "end_reason": t.end_reason, "notes": t.notes,
    }


@router.post("/timer-sessions", status_code=201)
def start_timer_session(data: TimerStartIn, session: Session = Depends(get_session)):
    t = models.TimerSession(subject_id=data.subject_id, started_at=data.started_at)
    session.add(t)
    session.commit()
    return _timer_out(session, t)


@router.patch("/timer-sessions/{timer_id}")
def update_timer_session(timer_id: int, data: TimerPatchIn, session: Session = Depends(get_session)):
    t = session.get(models.TimerSession, timer_id)
    if t is None:
        raise HTTPException(404, "sessão do cronômetro não encontrada")
    fields = data.model_dump(exclude_unset=True)
    if "subject_id" in fields:
        t.subject_id = data.subject_id
    if data.pauses is not None:
        t.pauses = data.pauses
    if data.notes is not None:
        t.notes = data.notes
    if data.end_reason and t.end_reason is None:
        t.end_reason = data.end_reason
        t.ended_at = data.ended_at or datetime.now()
        t.wall_seconds = max(0, int((t.ended_at - t.started_at).total_seconds()))
        t.active_seconds = sum(session.scalars(select(models.StudySession.seconds)
                                               .where(models.StudySession.timer_session_id == t.id)).all())
    session.commit()
    return _timer_out(session, t)


@router.delete("/timer-sessions/{timer_id}", status_code=204)
def cancel_timer_session(timer_id: int, session: Session = Depends(get_session)):
    """v1.7.2: Cancelar no cronômetro descarta a sessão e os trechos dela (não contam nas horas)."""
    t = session.get(models.TimerSession, timer_id)
    if t is None:
        raise HTTPException(404, "sessão do cronômetro não encontrada")
    for chunk in session.scalars(select(models.StudySession)
                                 .where(models.StudySession.timer_session_id == timer_id)).all():
        session.delete(chunk)
    session.delete(t)
    session.commit()


@router.get("/timer-sessions")
def list_timer_sessions(limit: int = Query(30, le=1000), area: areas.Area | None = "faculdade",
                        session: Session = Depends(get_session)):
    subjects = {s.id: s.name for s in session.scalars(select(models.Subject)).all()}
    course_ids = areas.course_subject_ids(session)
    rows = session.scalars(select(models.TimerSession).order_by(models.TimerSession.started_at.desc())).all()
    rows = [t for t in rows if areas.in_area(t.subject_id, area, course_ids)][:limit]
    return [_timer_out(session, t, subjects) for t in rows]


# --- Histórico ---------------------------------------------------------------


def _set_row(session: Session, qs: models.QuestionSet, topics: dict[int, models.Topic],
             subjects: dict[int, str]) -> dict:
    topic = topics.get(qs.topic_id) if qs.topic_id else None
    subject_id = topic.subject_id if topic else qs.subject_id
    valid = [q for q in qs.questions if not q.flagged_bad]
    answered = [q for q in valid if q.answer is not None]
    right = sum(1 for q in answered if q.answer.is_correct)
    return {
        "id": qs.id, "topic_id": qs.topic_id,
        "topic_title": topic.title if topic else ("Erros para refazer" if qs.attempt_type == "redo" else "Simulado"),
        "subject_id": subject_id, "subject_name": subjects.get(subject_id),
        "attempt_type": qs.attempt_type, "label": learning.LABELS.get(qs.attempt_type, qs.attempt_type),
        "score": qs.score, "questions": len(valid), "answered": len(answered), "right": right,
        "wrong": len(answered) - right, "created_at": qs.created_at.isoformat() if qs.created_at else None,
        "completed_at": qs.completed_at.isoformat() if qs.completed_at else None,
        "time_limit_minutes": qs.time_limit_minutes, "model": qs.model,
    }


@router.get("/history")
def history(subject_id: int | None = None, topic_id: int | None = None, limit: int = Query(200, le=500),
            area: areas.Area | None = "faculdade", session: Session = Depends(get_session)):
    """Todos os conjuntos de questões, do mais novo para o mais antigo."""
    topics = {t.id: t for t in session.scalars(select(models.Topic)).all()}
    subjects = {s.id: s.name for s in session.scalars(select(models.Subject)).all()}
    stmt = (select(models.QuestionSet)
            .options(selectinload(models.QuestionSet.questions).selectinload(models.Question.answer))
            .order_by(models.QuestionSet.created_at.desc(), models.QuestionSet.id.desc()))
    if topic_id is not None:
        stmt = stmt.where(models.QuestionSet.topic_id == topic_id)
    course_ids = areas.course_subject_ids(session)
    rows = [_set_row(session, qs, topics, subjects) for qs in session.scalars(stmt).all()]
    rows = [r for r in rows if areas.in_area(r["subject_id"], area, course_ids)]
    if subject_id is not None:
        rows = [r for r in rows if r["subject_id"] == subject_id]
    return rows[:limit]


@router.get("/history/topics")
def topic_evolution(area: areas.Area | None = "faculdade", session: Session = Depends(get_session)):
    """Evolução por tema: todas as notas concluídas em ordem, mais o status e os erros em aberto."""
    out = []
    course_ids = areas.course_subject_ids(session)
    topics = session.scalars(select(models.Topic).options(selectinload(models.Topic.subject))
                             .order_by(models.Topic.subject_id, models.Topic.position)).all()
    for t in topics:
        if not areas.in_area(t.subject_id, area, course_ids):
            continue
        sets = session.scalars(select(models.QuestionSet)
                               .where(models.QuestionSet.topic_id == t.id, models.QuestionSet.completed_at.is_not(None))
                               .order_by(models.QuestionSet.completed_at)).all()
        if not sets:
            continue
        mistakes = learning.mistake_counts(session, topic_id=t.id)
        out.append({
            "topic_id": t.id, "topic_title": t.title, "subject_id": t.subject_id, "subject_name": t.subject.name,
            "status": t.learning_status, "has_text": bool(t.source_text), "mistakes": mistakes,
            # Compatibilidade: erros que ainda pedem revisão (não revisados + revisar de novo)
            "open_mistakes": mistakes["open"] + mistakes["again"],
            # v1.6: cards do tema (total e vencidos hoje)
            "cards": len(session.scalars(select(models.Card.id).where(models.Card.topic_id == t.id)).all()),
            "points": [{"set_id": s.id, "date": s.completed_at.date().isoformat(), "score": s.score,
                        "label": learning.LABELS.get(s.attempt_type, s.attempt_type)} for s in sets],
        })
    return out


# --- Resumo da semana (D20) --------------------------------------------------


@router.get("/week")
def week_summary(today: date | None = Query(None, description="Só para testes; padrão = hoje"),
                 session: Session = Depends(get_session)):
    today = today or date.today()
    start = today - timedelta(days=today.weekday())  # segunda-feira
    begin, end = datetime.combine(start, time.min), datetime.combine(start + timedelta(days=7), time.min)
    course_ids = areas.course_subject_ids(session)
    seconds = sum(r.seconds for r in session.scalars(select(models.StudySession).where(
        models.StudySession.started_at >= begin, models.StudySession.started_at < end)).all()
        if areas.in_area(r.subject_id, "faculdade", course_ids))
    sets = session.scalars(select(models.QuestionSet).where(
        models.QuestionSet.completed_at >= begin, models.QuestionSet.completed_at < end)).all()
    scores = [s.score for s in sets if s.score is not None]
    learned = {s.topic_id for s in sets if s.attempt_type in learning.DECISIVE and s.topic_id
               and session.get(models.Topic, s.topic_id).learning_status == "learned"}
    done = (len(session.scalars(select(models.Deadline.id).where(
        models.Deadline.done_at >= begin, models.Deadline.done_at < end)).all())
            + len(session.scalars(select(models.Exam.id).where(
                models.Exam.done_at >= begin, models.Exam.done_at < end)).all()))
    return {
        "start": start.isoformat(), "seconds": seconds, "sets": len(sets),
        "average_score": sum(scores) / len(scores) if scores else None,
        "topics_learned": len(learned), "items_done": done,
    }


# --- Backup diário (D20) -----------------------------------------------------

KEEP_BACKUPS = 14


def daily_backup(db_path: Path | None = None, today: date | None = None) -> Path | None:
    """Copia o banco para ./data/backups/painel-AAAA-MM-DD.db uma vez por dia; guarda os últimos 14.

    Usa a API de backup do SQLite (cópia consistente mesmo com o app aberto).
    """
    if db_path is None:
        if os.environ.get("PAINEL_DATABASE_URL"):
            return None  # banco fora do padrão (testes): sem backup
        db_path = Path(os.environ.get("PAINEL_DB_PATH", "./data/painel.db"))
    if not db_path.exists():
        return None
    folder = db_path.parent / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"painel-{(today or date.today()).isoformat()}.db"
    if not target.exists():
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(target)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
    for old in sorted(folder.glob("painel-*.db"))[:-KEEP_BACKUPS]:
        old.unlink()
    return target


# --- Métricas de desempenho (D25) --------------------------------------------


def compute_metrics(session: Session, today: date, days: int = 30, subject_id: int | None = None,
                    area: areas.Area = "faculdade") -> dict:
    """Números do dashboard de desempenho; o agente usa um resumo deles quando liberado.

    v1.5: `subject_id` filtra horas, testes e notas por disciplina (os gráficos interativos usam).
    """
    start = today - timedelta(days=days - 1)
    begin, end = datetime.combine(start, time.min), datetime.combine(today + timedelta(days=1), time.min)
    subjects = {s.id: s for s in session.scalars(select(models.Subject)).all()}
    topics = {t.id: t for t in session.scalars(select(models.Topic)).all()}

    chunks = session.scalars(select(models.StudySession).where(
        models.StudySession.started_at >= begin, models.StudySession.started_at < end)).all()
    sets = session.scalars(select(models.QuestionSet)
                           .options(selectinload(models.QuestionSet.questions).selectinload(models.Question.answer))
                           .where(models.QuestionSet.completed_at >= begin, models.QuestionSet.completed_at < end)
                           .order_by(models.QuestionSet.completed_at)).all()

    def set_subject(qs: models.QuestionSet) -> int | None:
        return topics[qs.topic_id].subject_id if qs.topic_id in topics else qs.subject_id

    # v1.8 (D38): cada área tem os seus números
    course_ids = areas.course_subject_ids(session)
    chunks = [c for c in chunks if areas.in_area(c.subject_id, area, course_ids)]
    sets = [qs for qs in sets if areas.in_area(set_subject(qs), area, course_ids)]
    if subject_id is not None:
        chunks = [c for c in chunks if c.subject_id == subject_id]
        sets = [qs for qs in sets if set_subject(qs) == subject_id]

    daily = {start + timedelta(days=i): {"seconds": 0, "sets": 0, "scores": []} for i in range(days)}
    for c in chunks:
        daily[c.started_at.date()]["seconds"] += c.seconds
    answered = right = 0
    for qs in sets:
        d = daily[qs.completed_at.date()]
        d["sets"] += 1
        if qs.score is not None:
            d["scores"].append(qs.score)
        for q in qs.questions:
            if q.answer is not None and not q.flagged_bad:
                answered += 1
                right += int(q.answer.is_correct)

    # Sequência de dias seguidos com estudo (cronômetro ou teste), terminando hoje ou ontem
    active_days = {d for d, v in daily.items() if v["seconds"] > 0 or v["sets"] > 0}
    streak, cursor = 0, today if today in active_days else today - timedelta(days=1)
    while cursor in active_days:
        streak += 1
        cursor -= timedelta(days=1)

    if area == "cursos":
        # Módulos dos cursos em andamento
        current = [s for s in subjects.values() if s.id in course_ids and s.degree.course_status == "doing"]
    else:
        current = [s for s in subjects.values() if s.semester and s.semester.is_current]
    by_subject = []
    for s in sorted(current, key=lambda x: x.name):
        s_sets = [qs for qs in sets if set_subject(qs) == s.id and qs.score is not None]
        s_topics = [t for t in topics.values() if t.subject_id == s.id]
        by_subject.append({
            "subject_id": s.id, "name": s.name,
            "seconds": sum(c.seconds for c in chunks if c.subject_id == s.id),
            "sets": len(s_sets),
            "average_score": sum(q.score for q in s_sets) / len(s_sets) if s_sets else None,
            "topics_total": len(s_topics),
            "topics_learned": sum(1 for t in s_topics if t.learning_status == "learned"),
            "topics_review": sum(1 for t in s_topics if t.learning_status == "review"),
            **_mistake_fields(learning.mistake_counts(session, subject_id=s.id)),
        })

    timers = session.scalars(select(models.TimerSession).where(
        models.TimerSession.started_at >= begin, models.TimerSession.started_at < end,
        models.TimerSession.end_reason.is_not(None))).all()
    timers = [t for t in timers if areas.in_area(t.subject_id, area, course_ids)]
    if subject_id is not None:
        timers = [t for t in timers if t.subject_id == subject_id]
    wall = sum(t.wall_seconds or 0 for t in timers)
    active = sum(t.active_seconds for t in timers)

    graded = []
    for d in session.scalars(select(models.Deadline).where(models.Deadline.score.is_not(None))).all():
        if subject_id is not None and d.subject_id != subject_id:
            continue
        if not areas.in_area(d.subject_id, area, course_ids):
            continue
        graded.append({"title": d.title, "kind": KIND_LABELS.get(d.kind, d.kind), "score": d.score,
                       "max_score": SCORE_SCALE.get(d.kind, 10.0),
                       "wrong_attempts": d.wrong_attempts, "date": d.due_date.isoformat()})
    for e in session.scalars(select(models.Exam).where(models.Exam.score.is_not(None))).all():
        if subject_id is not None and e.subject_id != subject_id:
            continue
        if not areas.in_area(e.subject_id, area, course_ids):
            continue
        when = e.scheduled_at.date() if e.scheduled_at else e.schedule_by
        graded.append({"title": f"{e.kind} · {subjects[e.subject_id].name}", "kind": "Prova", "score": e.score,
                       "max_score": 10.0, "wrong_attempts": None, "date": when.isoformat() if when else None})

    all_scores = [qs.score for qs in sets if qs.score is not None]
    # v1.6 (D37): cards revisados por dia (filtrados pela disciplina, se houver)
    card_days = _card_reviews_by_day(session, begin, end, subject_id, area, course_ids)
    return {
        "start": start.isoformat(), "end": today.isoformat(), "days": days, "subject_id": subject_id, "area": area,
        "totals": {
            "seconds": sum(v["seconds"] for v in daily.values()), "sets": len(sets),
            "questions": answered, "accuracy": right / answered if answered else None,
            "average_score": sum(all_scores) / len(all_scores) if all_scores else None,
            "study_days": len(active_days), "streak": streak,
            "cards_reviewed": sum(card_days.values()),
        },
        "daily": [{"date": d.isoformat(), "seconds": v["seconds"], "sets": v["sets"],
                   "cards": card_days.get(d.isoformat(), 0),
                   "average_score": sum(v["scores"]) / len(v["scores"]) if v["scores"] else None}
                  for d, v in daily.items()],
        "scores": [{"set_id": qs.id, "date": qs.completed_at.isoformat(), "score": qs.score,
                    "attempt_type": qs.attempt_type,
                    "topic": topics[qs.topic_id].title if qs.topic_id in topics else None,
                    "label": learning.LABELS.get(qs.attempt_type, qs.attempt_type),
                    "subject": subjects[set_subject(qs)].name if set_subject(qs) in subjects else None}
                   for qs in sets],
        "by_subject": by_subject,
        "topics": {k: sum(1 for t in topics.values() if t.learning_status == k
                          and t.subject_id in {s.id for s in current})
                   for k in ("pending", "review", "learned")},
        "timer": {
            "sessions": len(timers), "active_seconds": active, "wall_seconds": wall,
            "average_active": active // len(timers) if timers else None,
            "average_pauses": sum(t.pauses for t in timers) / len(timers) if timers else None,
            "focus": active / wall if wall else None,
        },
        "graded": sorted(graded, key=lambda g: g["date"] or ""),
    }


def _card_reviews_by_day(session: Session, begin: datetime, end: datetime, subject_id: int | None,
                         area: areas.Area | None = None, course_ids: set[int] | None = None) -> dict[str, int]:
    stmt = (select(models.CardReview.created_at, models.Topic.subject_id).join(models.Card, models.Card.id == models.CardReview.card_id)
            .join(models.Topic, models.Topic.id == models.Card.topic_id)
            .where(models.CardReview.created_at >= begin, models.CardReview.created_at < end))
    if subject_id is not None:
        stmt = stmt.where(models.Topic.subject_id == subject_id)
    out: dict[str, int] = {}
    for at, sid in session.execute(stmt).all():
        if not areas.in_area(sid, area, course_ids or set()):
            continue
        out[at.date().isoformat()] = out.get(at.date().isoformat(), 0) + 1
    return out


def _mistake_fields(c: dict) -> dict:
    return {"mistakes": c, "open_mistakes": c["open"] + c["again"]}


@router.get("/metrics")
def metrics(days: int = Query(30, ge=7, le=180), subject_id: int | None = None, area: areas.Area = "faculdade",
            today: date | None = Query(None, description="Só para testes"),
            session: Session = Depends(get_session)):
    return compute_metrics(session, today or date.today(), days, subject_id, area)


@router.get("/day")
def day_detail(day: date, subject_id: int | None = None, area: areas.Area | None = "faculdade",
               session: Session = Depends(get_session)):
    """v1.5: o que foi feito num dia (clique na barra do gráfico de horas): trechos do cronômetro, testes e
    (v1.7.2) as tarefas do checklist daquele dia."""
    begin, end = datetime.combine(day, time.min), datetime.combine(day + timedelta(days=1), time.min)
    subjects = {s.id: s.name for s in session.scalars(select(models.Subject)).all()}
    topics = {t.id: t for t in session.scalars(select(models.Topic)).all()}
    stmt = select(models.StudySession).where(models.StudySession.started_at >= begin,
                                            models.StudySession.started_at < end)
    if subject_id is not None:
        stmt = stmt.where(models.StudySession.subject_id == subject_id)
    course_ids = areas.course_subject_ids(session)
    chunks = [c for c in session.scalars(stmt.order_by(models.StudySession.started_at)).all()
              if areas.in_area(c.subject_id, area, course_ids)]
    sets = session.scalars(select(models.QuestionSet)
                           .options(selectinload(models.QuestionSet.questions).selectinload(models.Question.answer))
                           .where(models.QuestionSet.completed_at >= begin, models.QuestionSet.completed_at < end)
                           .order_by(models.QuestionSet.completed_at)).all()
    rows = [r for r in (_set_row(session, qs, topics, subjects) for qs in sets)
            if areas.in_area(r["subject_id"], area, course_ids)]
    if subject_id is not None:
        rows = [r for r in rows if r["subject_id"] == subject_id]
    # v1.7.2: as tarefas do checklist ficam salvas com o dia; aqui elas aparecem de novo, feitas ou não
    items = session.scalars(select(models.ChecklistItem).where(models.ChecklistItem.day == day)
                            .order_by(models.ChecklistItem.position, models.ChecklistItem.id)).all()
    # Tarefa ligada a um tema fica na área do tema; tarefa solta fica na faculdade
    items = [i for i in items if areas.in_area(topics[i.topic_id].subject_id if topics.get(i.topic_id) else None,
                                               area, course_ids)]
    if subject_id is not None:
        items = [i for i in items if i.topic_id and topics.get(i.topic_id) and topics[i.topic_id].subject_id == subject_id]
    return {
        "date": day.isoformat(),
        "seconds": sum(c.seconds for c in chunks),
        "tasks": [{"id": i.id, "label": i.label, "done": i.done, "planned_minutes": i.planned_minutes} for i in items],
        "chunks": [{"started_at": c.started_at.isoformat(), "ended_at": c.ended_at.isoformat() if c.ended_at else None,
                    "seconds": c.seconds, "subject_name": subjects.get(c.subject_id) if c.subject_id else None}
                   for c in chunks],
        "sets": rows,
    }


def metrics_text(session: Session, today: date | None = None) -> str:
    """Resumo curto das métricas dos últimos 30 dias, em texto, para o agente (só se liberado)."""
    m = compute_metrics(session, today or date.today(), 30)
    t = m["totals"]
    pct = lambda v: "—" if v is None else f"{round(v * 100)}%"  # noqa: E731
    lines = [
        f"Últimos 30 dias: {round(t['seconds'] / 3600, 1)} h estudadas em {t['study_days']} dias "
        f"(sequência atual: {t['streak']} dias); {t['sets']} testes, acerto médio {pct(t['accuracy'])}.",
        f"Temas do semestre: {m['topics']['learned']} aprendidos, {m['topics']['review']} para revisar, "
        f"{m['topics']['pending']} em andamento.",
    ]
    for s in m["by_subject"]:
        lines.append(f"- {s['name']}: {round(s['seconds'] / 3600, 1)} h, {s['sets']} testes, nota média "
                     f"{pct(s['average_score'])}, {s['topics_learned']}/{s['topics_total']} temas aprendidos, "
                     f"erros: {s['mistakes']['open']} não revisados, {s['mistakes']['reviewed']} revisados "
                     f"(falta acertar), {s['mistakes']['again']} para revisar de novo, "
                     f"{s['mistakes']['fixed']} corrigidos.")
    tm = m["timer"]
    if tm["sessions"]:
        lines.append(f"Cronômetro: {tm['sessions']} sessões, foco {pct(tm['focus'])} do tempo, "
                     f"{tm['average_pauses']:.1f} pausas por sessão.")
    return "\n".join(lines)
