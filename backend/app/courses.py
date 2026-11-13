"""v1.8: cursos e certificados fora da faculdade (SPEC §18, D38–D44).

Um curso é uma `degree` com kind "course". Módulos = disciplinas sem semestre; aulas = temas. Assim questões,
cards, cronômetro, histórico e o ciclo dos erros funcionam nos cursos sem código novo, só filtrados por área.
"""

import re
from datetime import date, datetime, time, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import areas, models, settings_store
from .db import get_session

router = APIRouter(prefix="/api/courses", tags=["cursos e certificados"])

CourseType = Literal["course_certificate", "certification", "language", "bootcamp", "free"]
CourseStatus = Literal["wishlist", "doing", "paused", "done"]
TYPE_LABELS = {
    "course_certificate": "curso com certificado", "certification": "certificação com prova",
    "language": "idioma", "bootcamp": "bootcamp", "free": "curso livre",
}
STATUS_LABELS = {"wishlist": "Quero fazer", "doing": "Fazendo", "paused": "Pausado", "done": "Concluído"}
NOTION_ID = re.compile(r"([0-9a-f]{32})(?:[?#].*)?$", re.I)


def notion_id(value: str | None) -> str | None:
    """Aceita o link da página ou o id (32 caracteres hex, com ou sem hífens)."""
    if not value:
        return None
    m = NOTION_ID.search(value.strip().replace("-", ""))
    if not m:
        raise ValueError("Cole o link da página do Notion ou o id dela.")
    return m.group(1).lower()


class CourseIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    platform: str | None = Field(default=None, max_length=100)
    course_type: CourseType = "course_certificate"
    url: str | None = Field(default=None, max_length=500)
    course_status: CourseStatus = "doing"
    total_hours: int | None = Field(default=None, ge=0, le=10_000)
    start_date: date | None = None
    target_date: date | None = None
    certificate_path: str | None = Field(default=None, max_length=500)
    counts_acc: bool = False
    acc_category: str | None = Field(default=None, max_length=100)
    notion_page: str | None = Field(default=None, max_length=300)
    exam_at: datetime | None = None
    manual_progress: int | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("url")
    @classmethod
    def _https(cls, v: str | None) -> str | None:
        if v and not v.strip().lower().startswith("https://"):
            raise ValueError("O link do curso precisa começar com https://")
        return v.strip() if v else None

    @field_validator("notion_page")
    @classmethod
    def _notion(cls, v: str | None) -> str | None:
        return notion_id(v)


class CourseCreate(CourseIn):
    # Quantos módulos criar ("Módulo 1", "Módulo 2"…); 0 = curso sem módulos (progresso manual)
    modules: int = Field(default=0, ge=0, le=50)


def _apply(c: models.Degree, data: CourseIn) -> None:
    fields = data.model_dump(exclude={"notion_page", "modules"})
    for key, value in fields.items():
        setattr(c, key, value)
    c.notion_page_id = data.notion_page
    if data.course_status == "done" and c.finished_on is None:
        c.finished_on = date.today()
    if data.course_status != "done":
        c.finished_on = None
    c.status = "finished" if data.course_status == "done" else "active"


def _get_course(session: Session, course_id: int) -> models.Degree:
    c = session.get(models.Degree, course_id)
    if c is None or c.kind == "degree":
        raise HTTPException(404, "curso não encontrado")
    return c


def _modules(session: Session, course_id: int) -> list[models.Subject]:
    return list(session.scalars(select(models.Subject).options(selectinload(models.Subject.topics))
                                .where(models.Subject.degree_id == course_id).order_by(models.Subject.id)).all())


def _seconds(session: Session, subject_ids: list[int], begin: datetime | None = None) -> int:
    if not subject_ids:
        return 0
    stmt = select(models.StudySession.seconds).where(models.StudySession.subject_id.in_(subject_ids))
    if begin is not None:
        stmt = stmt.where(models.StudySession.started_at >= begin)
    return sum(session.scalars(stmt).all())


def _week_start(today: date) -> datetime:
    return datetime.combine(today - timedelta(days=today.weekday()), time.min)


def _last_score(session: Session, topic_id: int) -> float | None:
    qs = session.scalars(select(models.QuestionSet).where(
        models.QuestionSet.topic_id == topic_id, models.QuestionSet.completed_at.is_not(None))
        .order_by(models.QuestionSet.completed_at.desc())).first()
    return qs.score if qs else None


def next_lesson(modules: list[models.Subject]) -> dict | None:
    """Primeira aula não vista do primeiro módulo não concluído."""
    for i, m in enumerate(modules, start=1):
        if m.status == "passed":
            continue
        for t in m.topics:
            if not t.portal_done:
                return {"module_id": m.id, "module": m.name, "module_number": i, "topic_id": t.id, "title": t.title}
        return {"module_id": m.id, "module": m.name, "module_number": i, "topic_id": None, "title": None}
    return None


def course_out(session: Session, c: models.Degree, today: date, detail: bool = False) -> dict:
    modules = _modules(session, c.id)
    ids = [m.id for m in modules]
    done = sum(1 for m in modules if m.status == "passed")
    progress = round(done / len(modules) * 100) if modules else (c.manual_progress or 0)
    if c.course_status == "done":
        progress = 100
    sets = session.scalars(select(models.QuestionSet).join(models.Topic, models.Topic.id == models.QuestionSet.topic_id)
                           .where(models.Topic.subject_id.in_(ids), models.QuestionSet.completed_at.is_not(None))
                           ).all() if ids else []
    scores = [s.score for s in sets if s.score is not None]
    cards = session.scalars(select(models.Card.id).join(models.Topic, models.Topic.id == models.Card.topic_id)
                            .where(models.Topic.subject_id.in_(ids))).all() if ids else []
    out = {
        "id": c.id, "name": c.name, "platform": c.platform, "course_type": c.course_type or "free",
        "type_label": TYPE_LABELS.get(c.course_type or "free", "curso"), "url": c.url,
        "course_status": c.course_status or "doing",
        "status_label": STATUS_LABELS.get(c.course_status or "doing", ""), "total_hours": c.total_hours,
        "start_date": c.start_date.isoformat() if c.start_date else None,
        "target_date": c.target_date.isoformat() if c.target_date else None,
        "days_to_target": (c.target_date - today).days if c.target_date else None,
        "certificate_path": c.certificate_path, "counts_acc": c.counts_acc, "acc_category": c.acc_category,
        "notion_page_id": c.notion_page_id,
        "notion_url": f"https://www.notion.so/{c.notion_page_id}" if c.notion_page_id else None,
        "exam_at": c.exam_at.isoformat() if c.exam_at else None,
        "days_to_exam": (c.exam_at.date() - today).days if c.exam_at else None,
        "manual_progress": c.manual_progress, "notes": c.notes,
        "finished_on": c.finished_on.isoformat() if c.finished_on else None,
        "acc_activity_id": c.acc_activity_id,
        "modules_total": len(modules), "modules_done": done, "progress": progress,
        "seconds": _seconds(session, ids), "week_seconds": _seconds(session, ids, _week_start(today)),
        "sets": len(sets), "average_score": sum(scores) / len(scores) if scores else None, "cards": len(cards),
        "next_lesson": next_lesson(modules),
    }
    if detail:
        out["modules"] = [{
            "id": m.id, "name": m.name, "status": m.status, "number": i,
            "lessons": [{"id": t.id, "title": t.title, "done": t.portal_done, "has_text": bool(t.source_text),
                         "last_score": _last_score(session, t.id), "notion_page_id": t.notion_page_id,
                         "learning_status": t.learning_status} for t in m.topics],
        } for i, m in enumerate(modules, start=1)]
    return out


def _courses(session: Session) -> list[models.Degree]:
    return list(session.scalars(select(models.Degree).where(models.Degree.kind != "degree")
                                .order_by(models.Degree.id)).all())


@router.get("")
def list_courses(status: CourseStatus | None = None, today: date | None = Query(None),
                 session: Session = Depends(get_session)):
    today = today or date.today()
    rows = [c for c in _courses(session) if status is None or (c.course_status or "doing") == status]
    return [course_out(session, c, today) for c in rows]


@router.get("/summary")
def courses_summary(today: date | None = Query(None), session: Session = Depends(get_session)):
    """Resumo da área (Meus cursos): horas da semana contra a meta própria (D41), certificados, próxima prova."""
    today = today or date.today()
    courses = _courses(session)
    course_ids = areas.course_subject_ids(session)
    week = _seconds(session, list(course_ids), _week_start(today))
    done = [c for c in courses if c.course_status == "done"]
    acc_hours = 0.0
    for c in done:
        if c.acc_activity_id:
            a = session.get(models.AccActivity, c.acc_activity_id)
            acc_hours += a.hours if a else 0
    upcoming = sorted((c for c in courses if c.exam_at and c.exam_at.date() >= today and c.course_status != "done"),
                      key=lambda c: c.exam_at)
    nxt = upcoming[0] if upcoming else None
    counts = {k: sum(1 for c in courses if (c.course_status or "doing") == k) for k in STATUS_LABELS}
    return {
        "week_seconds": week, "goal_hours": settings_store.get(session, "course_weekly_goal_hours"),
        "certificates": len(done), "acc_hours": acc_hours, "counts": counts,
        "next_exam": {"course_id": nxt.id, "name": nxt.name, "exam_at": nxt.exam_at.isoformat(),
                      "days": (nxt.exam_at.date() - today).days} if nxt else None,
    }


@router.get("/modules")
def timer_modules(session: Session = Depends(get_session)):
    """Módulos dos cursos em andamento, para o cronômetro (grupo próprio, D41)."""
    out = []
    for c in _courses(session):
        if (c.course_status or "doing") != "doing":
            continue
        for m in _modules(session, c.id):
            out.append({"id": m.id, "name": m.name, "course_id": c.id, "course_name": c.name})
    return out


@router.post("", status_code=201)
def create_course(data: CourseCreate, session: Session = Depends(get_session)):
    c = models.Degree(kind="course", name=data.name)
    _apply(c, data)
    session.add(c)
    session.flush()
    for i in range(1, data.modules + 1):
        session.add(models.Subject(degree_id=c.id, name=f"Módulo {i}", status="pending"))
    session.commit()
    return course_out(session, c, date.today(), detail=True)


@router.get("/{course_id}")
def get_course(course_id: int, today: date | None = Query(None), session: Session = Depends(get_session)):
    return course_out(session, _get_course(session, course_id), today or date.today(), detail=True)


@router.put("/{course_id}")
def update_course(course_id: int, data: CourseIn, session: Session = Depends(get_session)):
    c = _get_course(session, course_id)
    _apply(c, data)
    session.commit()
    return course_out(session, c, date.today(), detail=True)


@router.delete("/{course_id}", status_code=204)
def delete_course(course_id: int, session: Session = Depends(get_session)):
    """Apaga o curso com módulos, aulas e testes dele (a tela pede confirmação). A AAC lançada continua."""
    session.delete(_get_course(session, course_id))
    session.commit()


class ModuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ModulePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    done: bool | None = None


@router.post("/{course_id}/modules", status_code=201)
def add_module(course_id: int, data: ModuleIn, session: Session = Depends(get_session)):
    c = _get_course(session, course_id)
    m = models.Subject(degree_id=c.id, name=data.name, status="pending")
    session.add(m)
    session.commit()
    return {"id": m.id, "name": m.name, "status": m.status}


def _get_module(session: Session, module_id: int) -> models.Subject:
    m = session.get(models.Subject, module_id)
    if m is None or m.degree.kind == "degree":
        raise HTTPException(404, "módulo não encontrado")
    return m


@router.patch("/modules/{module_id}")
def patch_module(module_id: int, data: ModulePatch, session: Session = Depends(get_session)):
    m = _get_module(session, module_id)
    if data.name is not None:
        m.name = data.name
    if data.done is not None:
        m.status = "passed" if data.done else ("in_progress" if any(t.portal_done for t in m.topics) else "pending")
    session.commit()
    return {"id": m.id, "name": m.name, "status": m.status}


class LessonIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)


class LessonPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    done: bool | None = None
    source_text: str | None = Field(default=None, max_length=200_000)
    notion_page: str | None = Field(default=None, max_length=300)

    @field_validator("notion_page")
    @classmethod
    def _notion(cls, v: str | None) -> str | None:
        return notion_id(v) if v else v


@router.post("/modules/{module_id}/lessons", status_code=201)
def add_lesson(module_id: int, data: LessonIn, session: Session = Depends(get_session)):
    m = _get_module(session, module_id)
    t = models.Topic(subject_id=m.id, title=data.title, position=len(m.topics) + 1)
    session.add(t)
    if m.status == "passed":
        m.status = "in_progress"
    session.commit()
    return {"id": t.id, "title": t.title, "done": t.portal_done}


@router.patch("/lessons/{lesson_id}")
def patch_lesson(lesson_id: int, data: LessonPatch, session: Session = Depends(get_session)):
    t = session.get(models.Topic, lesson_id)
    if t is None or t.subject.degree.kind == "degree":
        raise HTTPException(404, "aula não encontrada")
    if data.title is not None:
        t.title = data.title
    if data.source_text is not None:
        t.source_text = data.source_text or None
    if "notion_page" in data.model_fields_set:
        t.notion_page_id = data.notion_page or None
    if data.done is not None:
        t.portal_done = data.done
        m = t.subject
        session.flush()
        # Todas as aulas vistas = módulo concluído; uma desmarcada volta para em andamento
        if m.topics and all(x.portal_done for x in m.topics):
            m.status = "passed"
        elif any(x.portal_done for x in m.topics):
            m.status = "in_progress"
        else:
            m.status = "pending"
    session.commit()
    return {"id": t.id, "title": t.title, "done": t.portal_done, "module_status": t.subject.status}


@router.post("/{course_id}/acc", status_code=201)
def launch_acc(course_id: int, session: Session = Depends(get_session)):
    """D43: cria a atividade de AAC já preenchida a partir de um curso concluído, uma vez só."""
    c = _get_course(session, course_id)
    if not c.counts_acc:
        raise HTTPException(409, "Este curso não está marcado como AAC.")
    if c.course_status != "done":
        raise HTTPException(409, "Conclua o curso antes de lançar como AAC.")
    if c.acc_activity_id and session.get(models.AccActivity, c.acc_activity_id):
        raise HTTPException(409, "Este curso já foi lançado como AAC.")
    if not c.total_hours:
        raise HTTPException(409, "Informe a carga horária do curso antes de lançar como AAC.")
    college = session.scalars(select(models.Degree).where(models.Degree.kind == "degree",
                                                          models.Degree.status == "active")
                              .order_by(models.Degree.id)).first()
    if college is None:
        raise HTTPException(409, "Nenhuma graduação ativa para receber a AAC.")
    title = f"{c.platform} - {c.name}" if c.platform else c.name
    a = models.AccActivity(degree_id=college.id, title=title[:300], category=c.acc_category, hours=c.total_hours,
                           activity_date=c.finished_on or date.today(), certificate_path=c.certificate_path,
                           status="registered", notes="Lançada a partir de Meus cursos (v1.8, D43).")
    session.add(a)
    session.flush()
    c.acc_activity_id = a.id
    session.commit()
    return {"acc_activity_id": a.id, "title": a.title, "hours": a.hours}
