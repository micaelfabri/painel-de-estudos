"""v1.9 (D51): semestres em revisão — disciplinas encerradas que pedem revisão, com o motivo.

Quatro motivos, todos calculados com o que o Painel já guarda (nada é digitado à mão):
- failed: reprovada;
- not_learned: não aprendeu o suficiente (tema em "rever" ou média dos testes abaixo do limiar);
- not_consolidated: aprovada, mas sem consolidar (ciclo de retestes incompleto ou erros não corrigidos);
- not_seen_all: aprovada, mas não viu tudo (temas não concluídos no portal ou conteúdos abaixo do total).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import learning, models, settings_store
from .db import get_session

router = APIRouter(prefix="/api/review", tags=["revisão"])

REASONS = {
    "failed": "Não aprovado",
    "not_learned": "Não aprendeu o suficiente",
    "not_consolidated": "Aprovado, mas não consolidado",
    "not_seen_all": "Aprovado, mas não viu tudo",
}
FINISHED = ("passed", "failed")
MAX_TOPICS = 8  # temas listados por disciplina (os primeiros em ordem de prioridade)


def _pct(v: float) -> str:
    return f"{round(v * 100)}%"


def subject_review(session: Session, subject: models.Subject, threshold: float) -> dict | None:
    """Motivos de revisão de uma disciplina encerrada; None quando não há nenhum."""
    topics = sorted(subject.topics, key=lambda t: (t.position, t.id))
    tested: list[tuple[models.Topic, float | None]] = []
    for t in topics:
        sets = session.scalars(
            select(models.QuestionSet)
            .where(models.QuestionSet.topic_id == t.id, models.QuestionSet.completed_at.is_not(None),
                   models.QuestionSet.attempt_type.in_(learning.CYCLE))
            .order_by(models.QuestionSet.completed_at)
        ).all()
        if sets:
            tested.append((t, sets[-1].score))
    open_mistakes = {
        t.id: n for t in topics
        if (n := len(session.scalars(select(models.Mistake.id).where(
            models.Mistake.topic_id == t.id, models.Mistake.status.in_(learning.UNFIXED))).all()))
    }

    reasons: list[dict] = []
    why: dict[int, list[str]] = {}  # tema → motivos, para a lista de temas a rever

    def mark(t: models.Topic, text: str) -> None:
        why.setdefault(t.id, []).append(text)

    if subject.status == "failed":
        reasons.append({"key": "failed", "label": REASONS["failed"], "detail": "Disciplina reprovada."})

    # Não aprendeu o suficiente: tema em "rever" ou média dos últimos testes abaixo do limiar
    weak = [t for t, _ in tested if t.learning_status == "review"]
    scores = [s for _, s in tested if s is not None]
    avg = sum(scores) / len(scores) if scores else None
    low = [t for t, s in tested if s is not None and s < threshold and t not in weak]
    if weak or (avg is not None and avg < threshold):
        parts = []
        if weak:
            parts.append(f"{len(weak)} tema(s) em \"rever\"")
        if avg is not None:
            parts.append(f"média dos testes {_pct(avg)} (limiar {_pct(threshold)})")
        reasons.append({"key": "not_learned", "label": REASONS["not_learned"], "detail": "; ".join(parts) + "."})
        for t in weak:
            mark(t, "em \"rever\"")
        for t in low:
            mark(t, "último teste abaixo do limiar")

    if subject.status == "passed":
        # Aprovado, mas não consolidado: ciclo de retestes sem o reteste decisivo, ou erros não corrigidos
        unconsolidated = [t for t, _ in tested if t.learning_status == "pending"]
        if unconsolidated or open_mistakes:
            parts = []
            if unconsolidated:
                parts.append(f"{len(unconsolidated)} tema(s) sem o reteste de 7 dias")
            if open_mistakes:
                parts.append(f"{sum(open_mistakes.values())} erro(s) não corrigido(s)")
            reasons.append({"key": "not_consolidated", "label": REASONS["not_consolidated"],
                            "detail": "; ".join(parts) + "."})
            for t in unconsolidated:
                mark(t, "sem o reteste de 7 dias")
            for t in topics:
                if t.id in open_mistakes:
                    mark(t, f"{open_mistakes[t.id]} erro(s) não corrigido(s)")

        # Aprovado, mas não viu tudo: tema não concluído no portal ou conteúdos abaixo do total
        unseen = [t for t in topics if not t.portal_done]
        pp = subject.portal_progress
        short = (pp is not None and pp.contents_total and (pp.contents_done or 0) < pp.contents_total)
        if unseen or short:
            parts = []
            if unseen:
                parts.append(f"{len(unseen)} de {len(topics)} tema(s) não concluídos no portal")
            if short:
                parts.append(f"conteúdos {pp.contents_done or 0} de {pp.contents_total}")
            reasons.append({"key": "not_seen_all", "label": REASONS["not_seen_all"], "detail": "; ".join(parts) + "."})
            for t in unseen:
                mark(t, "não concluído no portal")

    if not reasons:
        return None
    to_review = [{"id": t.id, "title": t.title, "why": why[t.id], "has_text": bool(t.source_text or t.notion_page_id)}
                 for t in topics if t.id in why]
    return {
        "id": subject.id, "name": subject.name, "status": subject.status,
        "reasons": reasons,
        "topics": to_review[:MAX_TOPICS], "more_topics": max(0, len(to_review) - MAX_TOPICS),
        # v1.9.1: texto salvo ou página do Notion (as questões da disciplina leem a página na hora)
        "has_text": any(t.source_text or t.notion_page_id for t in topics),
    }


@router.get("")
def review_semesters(semester_id: int | None = Query(None), session: Session = Depends(get_session)):
    """Semestres com disciplinas encerradas que pedem revisão, do mais novo para o mais antigo."""
    threshold = float(settings_store.get(session, "learned_threshold"))
    college = select(models.Degree.id).where(models.Degree.kind == "degree")
    stmt = select(models.Subject).where(models.Subject.degree_id.in_(college), models.Subject.status.in_(FINISHED))
    if semester_id is not None:
        stmt = stmt.where(models.Subject.semester_id == semester_id)
    groups: dict[int | None, list[dict]] = {}
    for s in session.scalars(stmt.order_by(models.Subject.name)).all():
        info = subject_review(session, s, threshold)
        if info:
            groups.setdefault(s.semester_id, []).append(info)

    semesters = {x.id: x for x in session.scalars(select(models.Semester)).all()}
    out = []
    for sid, subjects in groups.items():
        sem = semesters.get(sid) if sid is not None else None
        out.append({
            "semester_id": sid, "code": sem.code if sem else None, "is_current": bool(sem and sem.is_current),
            "subjects": subjects,
            "counts": {k: sum(1 for x in subjects if any(r["key"] == k for r in x["reasons"])) for k in REASONS},
        })
    # Semestre mais novo primeiro; "sem semestre" no fim (sort estável: primeiro pelo código, depois o grupo)
    out.sort(key=lambda g: g["code"] or "", reverse=True)
    out.sort(key=lambda g: g["code"] is None)
    return {"reasons": REASONS, "semesters": out}
