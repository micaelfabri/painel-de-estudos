"""Carga inicial com DADOS FICTÍCIOS (cópia pública do projeto).

Uso: `python -m app.seed`. Não faz nada se já existir uma graduação cadastrada,
então é seguro rodar a cada início do container.

Curso, disciplinas, datas, local e horas são inventados para demonstração.
"""

from datetime import date, datetime

from sqlalchemy.orm import Session

from . import models
from .db import SessionLocal
from .grading import PRESETS

AS_OF = date(2026, 11, 9)
LOCATION = "Polo Centro"

# nome, horas, preset da regra, prova (data/hora) ou None, agendar até, exige lab, progresso do portal
CURRENT_SEMESTER = [
    {
        "name": "Engenharia de Requisitos", "hours": 80, "rule": "padrao_2026",
        "exam_at": datetime(2026, 11, 17, 17, 0), "lab": False,
        "progress": {"percent": 0, "contents": (0, 8), "exercises": (0, 5), "mocks": (0, 2)},
    },
    {
        "name": "Desenvolvimento Web", "hours": 60, "rule": "padrao_2026",
        "exam_at": datetime(2026, 11, 17, 18, 0), "lab": False,
        "progress": {"percent": 0, "contents": (0, 5), "exercises": (0, 4), "mocks": (0, 2)},
    },
    {
        "name": "Padrões de Projeto", "hours": 80, "rule": "padroes_java",
        "exam_at": datetime(2026, 11, 18, 16, 0), "lab": False,
        "progress": {"percent": 21, "contents": (2, 7), "exercises": (1, 5), "mocks": (0, 2)},
    },
    {
        "name": "Gestão de Produto", "hours": 80, "rule": "padrao_2026",
        "exam_at": datetime(2026, 11, 18, 17, 0), "lab": False,
        "progress": {"percent": 23, "contents": (2, 6), "exercises": (1, 5), "mocks": (0, 2)},
    },
    {
        "name": "Segurança de Software", "hours": 80, "rule": "padrao_2026",
        "exam_at": None, "schedule_by": date(2026, 11, 22), "lab": True,
        "progress": {"percent": 33, "contents": (3, 5), "exercises": (1, 4), "lab": (0, 1)},
    },
]

PENDING_SUBJECTS = [
    ("Estrutura de Dados", 80, None),
    ("Gerenciamento de Projetos", None, None),
    ("Métodos Quantitativos", None, None),
    ("Tópicos de Big Data em Python", None, None),
    ("Programação para Dispositivos Móveis em Android", None, None),
    ("Direito Cibernético", None, None),
    ("Computação em Nuvem", None, None),
    ("Programação em Python para Análise de Dados", None, None),
    ("Banco de Dados NoSQL", None, None),
    ("Métodos Ágeis com Scrum", None, "ESW0010"),
    ("Desenvolvimento de Front-End", None, None),
    ("Desenvolvimento de Back-End", None, None),
    ("Linhas de Produtos de Software", None, None),
    ("Qualidade e Testes de Software", None, None),
    ("Sistemas Distribuídos e Computação Paralela", None, None),
    ("DevOps", None, None),
]

# nome, exigidas, concluídas (fictício), tipo, a conferir, observação
COMPONENTS = [
    ("Mínima", 2860, 1040, "subjects", False, None),
    ("Extensionistas", 240, 144, "subjects", False, None),
    ("AAC", 100, 16, "acc", False, "Atividades complementares (ACC/AAC): soma das atividades cadastradas"),
    ("Optativa", 560, 0, "subjects", True, "Não fecha a soma das 3.200h; a conferir"),
    ("Estágio", None, 0, "manual", True, "Total exigido a definir"),
]


def seed(session: Session) -> models.Degree:
    degree = models.Degree(
        name="Engenharia de Software",
        institution="Universidade Exemplo",
        kind="degree",
        status="active",
        curriculum="2024",
        total_hours=3200,
        reported_done_hours=1200,
        reported_at=date(2026, 8, 10),
        expected_end="2028",
        notes="Dados fictícios para demonstração.",
    )
    session.add(degree)
    session.flush()

    components = {}
    for name, required, done, kind, to_check, notes in COMPONENTS:
        comp = models.DegreeComponent(
            degree_id=degree.id, name=name, required_hours=required, done_hours=done, kind=kind,
            to_check=to_check, notes=notes,
        )
        session.add(comp)
        components[name] = comp
    session.flush()

    semester = models.Semester(
        degree_id=degree.id, code="2026.3", is_current=True, notes="Semestre fictício"
    )
    session.add(semester)
    session.flush()

    for item in CURRENT_SEMESTER:
        subject = models.Subject(
            degree_id=degree.id,
            semester_id=semester.id,
            component_id=components["Mínima"].id,
            name=item["name"],
            hours=item["hours"],
            status="in_progress",
            grading_rule=PRESETS[item["rule"]],
            exam_requires_lab=item["lab"],
        )
        session.add(subject)
        session.flush()

        session.add(
            models.Exam(
                subject_id=subject.id,
                kind="AV",
                scheduled_at=item.get("exam_at"),
                schedule_by=item.get("schedule_by"),
                location=LOCATION,
            )
        )

        prog = item["progress"]
        pp = models.PortalProgress(subject_id=subject.id, percent=prog["percent"], as_of=AS_OF)
        for field in ("contents", "exercises", "mocks", "lab"):
            if field in prog:
                done, total = prog[field]
                setattr(pp, f"{field}_done", done)
                setattr(pp, f"{field}_total", total)
        session.add(pp)

        # Um tema por conteúdo do portal; os concluídos no portal vêm marcados
        done_contents, total_contents = prog["contents"]
        for n in range(1, total_contents + 1):
            session.add(
                models.Topic(subject_id=subject.id, position=n, title=f"Tema {n}", portal_done=n <= done_contents)
            )

    for name, hours, code in PENDING_SUBJECTS:
        is_ext = code == "ESW0010"
        session.add(
            models.Subject(
                degree_id=degree.id,
                semester_id=None,
                component_id=components["Extensionistas" if is_ext else "Mínima"].id,
                name=name,
                code=code,
                hours=hours,
                status="pending",
                grading_rule=PRESETS["extensionista" if is_ext else "padrao_2026"],
            )
        )

    session.add(
        models.AccActivity(
            degree_id=degree.id,
            title="Saldo inicial (exemplo)",
            hours=16,
            activity_date=date(2026, 8, 10),
            status="registered",
            notes="Total computado no histórico, sem detalhamento por atividade.",
        )
    )

    session.commit()
    return degree


def main() -> None:
    with SessionLocal() as session:
        if session.query(models.Degree).count() > 0:
            print("Banco já tem dados; carga inicial ignorada.")
            return
        seed(session)
        print("Carga inicial concluída.")


if __name__ == "__main__":
    main()
