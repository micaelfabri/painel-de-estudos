"""Progresso do curso e ACC (SPEC §6.5, §6.6).

Componente "subjects": horas do histórico (linha de base) + horas das disciplinas marcadas como
aprovadas no painel. Componente "acc": soma das atividades de ACC lançadas (registered), com o teto
por categoria quando houver regra. Componente "manual": só o valor digitado.
"""

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .db import get_session

router = APIRouter(prefix="/api/course", tags=["curso e ACC"])


def acc_summary(session: Session, degree_id: int, required: int | None) -> dict:
    activities = session.scalars(
        select(models.AccActivity).where(models.AccActivity.degree_id == degree_id)
        .order_by(models.AccActivity.activity_date)
    ).all()
    rules = {r.category: r for r in session.scalars(
        select(models.AccRule).where(models.AccRule.degree_id == degree_id)).all()}

    by_category: dict[str, dict] = defaultdict(lambda: {"registered": 0.0, "counted": 0.0, "planned": 0.0, "cap": None})
    for a in activities:
        cat = a.category or "Sem categoria"
        bucket = by_category[cat]
        rule = rules.get(a.category or "")
        hours = a.hours
        if rule and rule.max_hours_per_activity is not None:
            hours = min(hours, rule.max_hours_per_activity)
        if a.status == "registered":
            bucket["registered"] += a.hours
            bucket["counted"] += hours
        else:
            bucket["planned"] += a.hours
    for cat, bucket in by_category.items():
        rule = rules.get(cat)
        if rule and rule.max_hours is not None:
            bucket["cap"] = rule.max_hours
            bucket["counted"] = min(bucket["counted"], rule.max_hours)

    counted = sum(b["counted"] for b in by_category.values())
    return {
        "required_hours": required,
        "counted_hours": counted,
        "planned_hours": sum(b["planned"] for b in by_category.values()),
        "missing_hours": max(0.0, required - counted) if required is not None else None,
        "rules_known": bool(rules),
        "categories": [{"category": c, **b} for c, b in sorted(by_category.items())],
    }


@router.get("/progress")
def course_progress(degree_id: int | None = None, session: Session = Depends(get_session)):
    degree = session.get(models.Degree, degree_id) if degree_id else session.scalars(
        select(models.Degree).where(models.Degree.status == "active").order_by(models.Degree.id)).first()
    if degree is None:
        raise HTTPException(404, "nenhuma graduação cadastrada")

    passed = session.scalars(
        select(models.Subject).where(models.Subject.degree_id == degree.id, models.Subject.status == "passed")
    ).all()
    passed_by_component: dict[int | None, int] = defaultdict(int)
    for s in passed:
        passed_by_component[s.component_id] += s.hours or 0

    components = []
    acc = None
    for c in sorted(degree.components, key=lambda c: c.id):
        if c.kind == "acc":
            acc = acc_summary(session, degree.id, c.required_hours)
            done = acc["counted_hours"]
            from_panel = done
        elif c.kind == "subjects":
            from_panel = passed_by_component.get(c.id, 0)
            done = c.done_hours + from_panel
        else:
            from_panel = 0
            done = c.done_hours
        components.append({
            "id": c.id, "name": c.name, "kind": c.kind, "required_hours": c.required_hours,
            "baseline_hours": c.done_hours, "from_panel_hours": from_panel, "done_hours": done,
            "percent": round(done / c.required_hours * 100, 1) if c.required_hours else None,
            "to_check": c.to_check, "notes": c.notes,
        })

    done_total = sum(c["done_hours"] for c in components)
    semesters = session.scalars(
        select(models.Semester).where(models.Semester.degree_id == degree.id).order_by(models.Semester.code)).all()
    pending = session.scalars(
        select(models.Subject).where(models.Subject.degree_id == degree.id,
                                     models.Subject.status.in_(("pending", "in_progress", "failed")))
        .order_by(models.Subject.name)).all()
    return {
        "degree": {"id": degree.id, "name": degree.name, "institution": degree.institution,
                   "curriculum": degree.curriculum, "total_hours": degree.total_hours,
                   "reported_done_hours": degree.reported_done_hours,
                   "reported_at": degree.reported_at.isoformat() if degree.reported_at else None,
                   "expected_end": degree.expected_end},
        "done_hours": done_total,
        "percent": round(done_total / degree.total_hours * 100, 1) if degree.total_hours else None,
        "components": components,
        "acc": acc,
        "semesters": [{"id": s.id, "code": s.code, "is_current": s.is_current,
                       "subjects": [{"id": x.id, "name": x.name, "hours": x.hours, "status": x.status}
                                    for x in s.subjects]} for s in semesters],
        "unscheduled": [{"id": x.id, "name": x.name, "hours": x.hours, "status": x.status}
                        for x in pending if x.semester_id is None],
    }
