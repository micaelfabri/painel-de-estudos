"""Modelo de dados (SPEC §9).

Datas e horas são locais (America/Sao_Paulo), sem fuso gravado: o app roda
só no PC do dono. Status e tipos são texto validado pelos schemas Pydantic.
"""

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )


# --- Estrutura acadêmica -----------------------------------------------------


class Degree(TimestampMixin, Base):
    """Graduação ou curso paralelo (topo da hierarquia)."""

    __tablename__ = "degree"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    institution: Mapped[str | None] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), default="degree")  # degree | course | certificate
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | finished
    curriculum: Mapped[str | None] = mapped_column(String(50))
    total_hours: Mapped[int | None] = mapped_column(Integer)
    # Total concluído informado pela faculdade (histórico), com a data da fonte
    reported_done_hours: Mapped[int | None] = mapped_column(Integer)
    reported_at: Mapped[date | None] = mapped_column(Date)
    expected_end: Mapped[str | None] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text)

    components: Mapped[list["DegreeComponent"]] = relationship(back_populates="degree", cascade="all, delete-orphan")
    semesters: Mapped[list["Semester"]] = relationship(back_populates="degree", cascade="all, delete-orphan")
    subjects: Mapped[list["Subject"]] = relationship(back_populates="degree", cascade="all, delete-orphan")


class DegreeComponent(TimestampMixin, Base):
    """Componente da carga horária (mínima, extensionistas, AAC, optativa, estágio)."""

    __tablename__ = "degree_component"

    id: Mapped[int] = mapped_column(primary_key=True)
    degree_id: Mapped[int] = mapped_column(ForeignKey("degree.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    required_hours: Mapped[int | None] = mapped_column(Integer)
    # Horas concluídas segundo o histórico (linha de base); o painel soma o que for aprovado depois
    done_hours: Mapped[int] = mapped_column(Integer, default=0)
    # subjects = disciplinas aprovadas somam; acc = soma das atividades de ACC; manual = só o valor digitado
    kind: Mapped[str] = mapped_column(String(20), default="subjects", server_default="subjects")
    to_check: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    degree: Mapped[Degree] = relationship(back_populates="components")


class Semester(TimestampMixin, Base):
    __tablename__ = "semester"
    __table_args__ = (UniqueConstraint("degree_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    degree_id: Mapped[int] = mapped_column(ForeignKey("degree.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(20))  # ex.: 2026.3
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    degree: Mapped[Degree] = relationship(back_populates="semesters")
    subjects: Mapped[list["Subject"]] = relationship(back_populates="semester")


class Subject(TimestampMixin, Base):
    __tablename__ = "subject"

    id: Mapped[int] = mapped_column(primary_key=True)
    degree_id: Mapped[int] = mapped_column(ForeignKey("degree.id", ondelete="CASCADE"))
    semester_id: Mapped[int | None] = mapped_column(ForeignKey("semester.id", ondelete="SET NULL"))
    component_id: Mapped[int | None] = mapped_column(ForeignKey("degree_component.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str | None] = mapped_column(String(30))
    hours: Mapped[int | None] = mapped_column(Integer)
    # pending | in_progress | passed | failed
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # Regra de avaliação como dado (CLAUDE.md: nunca `if` por disciplina)
    grading_rule: Mapped[dict | None] = mapped_column(JSON)
    exam_requires_lab: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    degree: Mapped[Degree] = relationship(back_populates="subjects")
    semester: Mapped[Semester | None] = relationship(back_populates="subjects")
    topics: Mapped[list["Topic"]] = relationship(
        back_populates="subject", cascade="all, delete-orphan", order_by="Topic.position"
    )
    exams: Mapped[list["Exam"]] = relationship(back_populates="subject", cascade="all, delete-orphan")
    portal_progress: Mapped["PortalProgress | None"] = relationship(
        back_populates="subject", cascade="all, delete-orphan", uselist=False
    )


class PortalProgress(TimestampMixin, Base):
    """Progresso digitado a partir do portal da faculdade (SPEC D8)."""

    __tablename__ = "portal_progress"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subject.id", ondelete="CASCADE"), unique=True)
    percent: Mapped[float | None] = mapped_column(Float)
    contents_done: Mapped[int | None] = mapped_column(Integer)
    contents_total: Mapped[int | None] = mapped_column(Integer)
    exercises_done: Mapped[int | None] = mapped_column(Integer)
    exercises_total: Mapped[int | None] = mapped_column(Integer)
    mocks_done: Mapped[int | None] = mapped_column(Integer)
    mocks_total: Mapped[int | None] = mapped_column(Integer)
    lab_done: Mapped[int | None] = mapped_column(Integer)
    lab_total: Mapped[int | None] = mapped_column(Integer)
    as_of: Mapped[date | None] = mapped_column(Date)

    subject: Mapped[Subject] = relationship(back_populates="portal_progress")


class Topic(TimestampMixin, Base):
    __tablename__ = "topic"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subject.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(300))
    # Conteúdo marcado como concluído no portal (não é o mesmo que "aprendido")
    portal_done: Mapped[bool] = mapped_column(Boolean, default=False)
    # Status de aprendizado (SPEC §6.3): pending | learned | review
    learning_status: Mapped[str] = mapped_column(String(20), default="pending")
    notion_page_id: Mapped[str | None] = mapped_column(String(64))
    source_text: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    subject: Mapped[Subject] = relationship(back_populates="topics")


class Exam(TimestampMixin, Base):
    __tablename__ = "exam"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subject.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20), default="AV")  # AV | AVS | outro
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Quando a prova ainda precisa ser agendada: data limite
    schedule_by: Mapped[date | None] = mapped_column(Date)
    location: Mapped[str | None] = mapped_column(String(200))
    score: Mapped[float | None] = mapped_column(Float)
    gcal_event_id: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)

    subject: Mapped[Subject] = relationship(back_populates="exams")


class Deadline(TimestampMixin, Base):
    __tablename__ = "deadline"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subject.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(300))
    due_date: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(20), default="deadline")  # deadline | event
    gcal_event_id: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)


# --- Estudo e agente ---------------------------------------------------------


class StudySession(TimestampMixin, Base):
    """Sessão do cronômetro (SPEC §6.1)."""

    __tablename__ = "study_session"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topic.id", ondelete="SET NULL"))
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subject.id", ondelete="SET NULL"))
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Segundos efetivamente estudados (pausas descontadas)
    seconds: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text)


class QuestionSet(TimestampMixin, Base):
    __tablename__ = "question_set"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topic.id", ondelete="CASCADE"))
    # first | retest_1d | retest_7d | retest_21d | retest_3d (revisar)
    attempt_type: Mapped[str] = mapped_column(String(20), default="first")
    model: Mapped[str] = mapped_column(String(200))
    prompt_version: Mapped[str] = mapped_column(String(50))
    summary: Mapped[str | None] = mapped_column(Text)
    # Nota em 0..1, calculada sem as questões marcadas como ruins
    score: Mapped[float | None] = mapped_column(Float)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    # F5: quando o resultado foi gravado no fim da página do tema no Notion
    notion_synced_at: Mapped[datetime | None] = mapped_column(DateTime)

    questions: Mapped[list["Question"]] = relationship(
        back_populates="question_set", cascade="all, delete-orphan", order_by="Question.position"
    )


class Question(TimestampMixin, Base):
    __tablename__ = "question"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_set_id: Mapped[int] = mapped_column(ForeignKey("question_set.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    statement: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSON)
    correct_index: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str | None] = mapped_column(Text)
    flagged_bad: Mapped[bool] = mapped_column(Boolean, default=False)

    question_set: Mapped[QuestionSet] = relationship(back_populates="questions")
    answer: Mapped["Answer | None"] = relationship(back_populates="question", cascade="all, delete-orphan", uselist=False)


class Answer(TimestampMixin, Base):
    __tablename__ = "answer"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id", ondelete="CASCADE"), unique=True)
    chosen_index: Mapped[int] = mapped_column(Integer)
    is_correct: Mapped[bool] = mapped_column(Boolean)

    question: Mapped[Question] = relationship(back_populates="answer")


class Mistake(TimestampMixin, Base):
    """Registro de erros (SPEC §6.2), com o minuto do vídeo preenchido pelo dono."""

    __tablename__ = "mistake"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id", ondelete="CASCADE"), unique=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topic.id", ondelete="CASCADE"))
    video_minute: Mapped[str | None] = mapped_column(String(20))
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)


class ReviewSchedule(TimestampMixin, Base):
    """Retestes agendados (SPEC §6.3)."""

    __tablename__ = "review_schedule"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topic.id", ondelete="CASCADE"))
    attempt_type: Mapped[str] = mapped_column(String(20))
    due_date: Mapped[date] = mapped_column(Date)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    question_set_id: Mapped[int | None] = mapped_column(ForeignKey("question_set.id", ondelete="SET NULL"))


class ChecklistItem(TimestampMixin, Base):
    """Item do checklist do dia (exceção E11 do DS: marca na hora)."""

    __tablename__ = "checklist_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(Date)
    label: Mapped[str] = mapped_column(String(300))
    planned_minutes: Mapped[int | None] = mapped_column(Integer)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topic.id", ondelete="SET NULL"))
    # Item que é um reteste agendado (aponta para review_schedule)
    review_id: Mapped[int | None] = mapped_column(ForeignKey("review_schedule.id", ondelete="CASCADE"))
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)


# --- ACC ---------------------------------------------------------------------


class AccRule(TimestampMixin, Base):
    """Regra de ACC/AAC por categoria (valores pendentes do regulamento)."""

    __tablename__ = "acc_rule"

    id: Mapped[int] = mapped_column(primary_key=True)
    degree_id: Mapped[int] = mapped_column(ForeignKey("degree.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(100))
    max_hours: Mapped[int | None] = mapped_column(Integer)
    max_hours_per_activity: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)


class AccActivity(TimestampMixin, Base):
    __tablename__ = "acc_activity"

    id: Mapped[int] = mapped_column(primary_key=True)
    degree_id: Mapped[int] = mapped_column(ForeignKey("degree.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(300))
    category: Mapped[str | None] = mapped_column(String(100))
    hours: Mapped[float] = mapped_column(Float)
    activity_date: Mapped[date | None] = mapped_column(Date)
    certificate_path: Mapped[str | None] = mapped_column(String(500))
    # registered = lançada no portal | planned = ainda não lançada
    status: Mapped[str] = mapped_column(String(20), default="registered")
    notes: Mapped[str | None] = mapped_column(Text)


# --- Operação ----------------------------------------------------------------


class LlmCall(Base):
    """Registro de uso do modelo (SPEC §7)."""

    __tablename__ = "llm_call"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    model: Mapped[str] = mapped_column(String(200))
    prompt_name: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(50))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20))  # ok | invalid_json | error | cancelled
    error: Mapped[str | None] = mapped_column(Text)


class Setting(Base):
    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[object] = mapped_column(JSON)
