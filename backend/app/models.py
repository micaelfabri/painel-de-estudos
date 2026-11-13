"""Modelo de dados (SPEC §9).

Datas e horas são locais (America/Sao_Paulo), sem fuso gravado: o app roda
só no PC do dono. Status e tipos são texto validado pelos schemas Pydantic.
"""

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from .db import Base


# v1.7: o CURRENT_TIMESTAMP do SQLite é sempre UTC. O Python grava a hora local (TZ do contêiner,
# America/Sao_Paulo); o server_default fica só para linhas inseridas fora do ORM.
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, server_default=func.current_timestamp(), onupdate=datetime.now
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
    # v1.8 (D39): campos dos cursos fora da faculdade (kind = "course"); vazios numa graduação
    platform: Mapped[str | None] = mapped_column(String(100))
    # course_certificate | certification | language | bootcamp | free
    course_type: Mapped[str | None] = mapped_column(String(30))
    url: Mapped[str | None] = mapped_column(String(500))
    # wishlist | doing | paused | done
    course_status: Mapped[str | None] = mapped_column(String(20))
    start_date: Mapped[date | None] = mapped_column(Date)
    target_date: Mapped[date | None] = mapped_column(Date)
    certificate_path: Mapped[str | None] = mapped_column(String(500))
    counts_acc: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    acc_category: Mapped[str | None] = mapped_column(String(100))
    notion_page_id: Mapped[str | None] = mapped_column(String(64))
    exam_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Progresso digitado (0–100) para curso sem módulos, ex.: idioma
    manual_progress: Mapped[int | None] = mapped_column(Integer)
    finished_on: Mapped[date | None] = mapped_column(Date)
    # D43: atividade de AAC criada a partir deste curso (uma vez só)
    acc_activity_id: Mapped[int | None] = mapped_column(ForeignKey("acc_activity.id", ondelete="SET NULL"))

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
    # v1.3 (D14): marcada como feita no lado Estudo
    done_at: Mapped[datetime | None] = mapped_column(DateTime)

    subject: Mapped[Subject] = relationship(back_populates="exams")


class Deadline(TimestampMixin, Base):
    __tablename__ = "deadline"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subject.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(300))
    due_date: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(20), default="deadline")  # deadline | event | lab | activity | mock
    gcal_event_id: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    # v1.3 (D14, D17): concluído e resultado de labs/atividades (nota 0..10 = acertos de primeira ÷ total × 10)
    done_at: Mapped[datetime | None] = mapped_column(DateTime)
    total_questions: Mapped[int | None] = mapped_column(Integer)
    first_try_correct: Mapped[int | None] = mapped_column(Integer)
    wrong_attempts: Mapped[int | None] = mapped_column(Integer)
    score: Mapped[float | None] = mapped_column(Float)
    # v1.4: página do Notion do próprio item (ex.: o laboratório tem página própria no caderno)
    notion_page_id: Mapped[str | None] = mapped_column(String(64))


# --- Estudo e agente ---------------------------------------------------------


class TimerSession(TimestampMixin, Base):
    """v1.4 (D24): uma sessão do cronômetro do Iniciar até o Finalizar/Zerar, com os trechos dentro.

    active_seconds = soma dos trechos; wall_seconds = relógio "oculto" do início ao fim, pausas incluídas.
    """

    __tablename__ = "timer_session"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subject.id", ondelete="SET NULL"))
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    pauses: Mapped[int] = mapped_column(Integer, default=0)
    active_seconds: Mapped[int] = mapped_column(Integer, default=0)
    wall_seconds: Mapped[int | None] = mapped_column(Integer)
    # finished (Finalizar) | reset (Zerar, só sessões antigas; desde a v1.7.2 Cancelar apaga) | vazio = em andamento
    end_reason: Mapped[str | None] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text)


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
    # v1.4: sessão do cronômetro a que este trecho pertence
    timer_session_id: Mapped[int | None] = mapped_column(ForeignKey("timer_session.id", ondelete="SET NULL"))


class QuestionSet(TimestampMixin, Base):
    __tablename__ = "question_set"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Vazio só no simulado (D16), que mistura temas de uma disciplina
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topic.id", ondelete="CASCADE"))
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subject.id", ondelete="CASCADE"))
    # first | retest_1d | retest_7d | retest_21d | retest_3d (revisar)
    # v1.3 (D15, D16): redo (refazer erradas) | focus_errors | focus_hits | simulation
    attempt_type: Mapped[str] = mapped_column(String(20), default="first")
    # Conjunto de origem (refazer erradas) e tempo do simulado
    source_set_id: Mapped[int | None] = mapped_column(ForeignKey("question_set.id", ondelete="SET NULL"))
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer)
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
    # Tema da questão (no simulado cada questão vem de um tema); vazio = o tema do conjunto
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topic.id", ondelete="SET NULL"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    statement: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSON)
    correct_index: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str | None] = mapped_column(Text)
    flagged_bad: Mapped[bool] = mapped_column(Boolean, default=False)
    # v1.5: cópia de outra questão (refazer erradas); aponta sempre para a questão original
    source_question_id: Mapped[int | None] = mapped_column(ForeignKey("question.id", ondelete="SET NULL"))

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
    # v1.5 (D28): open (não revisado) | reviewed (revisado, falta acertar) | fixed (acertou depois) | again (errou de novo)
    status: Mapped[str] = mapped_column(String(20), default="open")
    notes: Mapped[str | None] = mapped_column(Text)

    @validates("reviewed")
    def _sync_status(self, _key: str, value: bool) -> bool:
        """Rota antiga (PUT /api/mistakes) ainda manda só `reviewed`: mantém o status do ciclo junto."""
        if value and self.status in (None, "open"):
            self.status = "reviewed"
        elif not value and self.status == "reviewed":
            self.status = "open"
        return value


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


class Card(Base):
    """v1.6 (D32–D37): card de estudo feito a partir dos meus pontos fracos."""

    __tablename__ = "card"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, server_default=func.current_timestamp())
    topic_id: Mapped[int] = mapped_column(ForeignKey("topic.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))  # concept | question | confusion
    mode: Mapped[str] = mapped_column(String(10), default="answer")  # answer (4 alternativas) | flip (virar)
    front: Mapped[str] = mapped_column(Text)
    back: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)
    options: Mapped[list | None] = mapped_column(JSON)
    correct_index: Mapped[int | None] = mapped_column(Integer)
    # Origem: mistake | text | print | video; o erro de origem liga o card ao ciclo dos erros (D33)
    source: Mapped[str] = mapped_column(String(10))
    mistake_id: Mapped[int | None] = mapped_column(ForeignKey("mistake.id", ondelete="SET NULL"))
    source_label: Mapped[str | None] = mapped_column(String(300))  # print ou arquivo de transcrição
    chosen_text: Mapped[str | None] = mapped_column(Text)  # o que marquei quando errei
    video_minute: Mapped[str | None] = mapped_column(String(10))
    step: Mapped[int] = mapped_column(Integer, default=0)
    next_review: Mapped[date] = mapped_column(Date, index=True)
    answer_streak: Mapped[int] = mapped_column(Integer, default=0)
    day_card_on: Mapped[date | None] = mapped_column(Date)  # card do dia (D37)
    prompt_version: Mapped[str | None] = mapped_column(String(80))
    notion_synced_at: Mapped[datetime | None] = mapped_column(DateTime)


class CardReview(Base):
    __tablename__ = "card_review"

    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("card.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, server_default=func.current_timestamp())
    mode: Mapped[str] = mapped_column(String(10))
    knew: Mapped[bool] = mapped_column(Boolean)
    chosen_index: Mapped[int | None] = mapped_column(Integer)


class ChatMessage(Base):
    """v1.5: conversa com o agente salva (não some ao recarregar a página)."""

    __tablename__ = "chat_message"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, server_default=func.current_timestamp())
    role: Mapped[str] = mapped_column(String(20))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topic.id", ondelete="SET NULL"))
    model: Mapped[str | None] = mapped_column(String(200))


class LlmCall(Base):
    """Registro de uso do modelo (SPEC §7)."""

    __tablename__ = "llm_call"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, server_default=func.current_timestamp())
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
