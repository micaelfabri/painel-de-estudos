"""v1.8 (D38): duas áreas no painel — a faculdade e os cursos fora dela.

Um curso é uma graduação (`degree`) com kind diferente de "degree". As páginas da faculdade filtram
`area="faculdade"` (padrão, nada muda para elas) e as de cursos `area="cursos"`. Itens sem disciplina
(ex.: cronômetro "Sem disciplina") ficam na faculdade.
"""

from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models

Area = Literal["faculdade", "cursos"]


def course_subject_ids(session: Session) -> set[int]:
    """Disciplinas (módulos) que pertencem a cursos fora da faculdade."""
    return set(session.scalars(
        select(models.Subject.id).join(models.Degree, models.Degree.id == models.Subject.degree_id)
        .where(models.Degree.kind != "degree")).all())


def in_area(subject_id: int | None, area: Area | None, course_ids: set[int]) -> bool:
    if area is None:
        return True
    is_course = subject_id is not None and subject_id in course_ids
    return is_course if area == "cursos" else not is_course


def topic_subjects(session: Session) -> dict[int, int]:
    """tema → disciplina, para filtrar o que só aponta para o tema (cards, erros, retestes)."""
    return dict(session.execute(select(models.Topic.id, models.Topic.subject_id)).all())
