"""Schemas Pydantic da API. `*In` = entrada (criar/editar), `*Out` = saída."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .grading import GradingRule


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Graduação ---------------------------------------------------------------


class DegreeIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    institution: str | None = None
    kind: Literal["degree", "course", "certificate"] = "degree"
    status: Literal["active", "finished"] = "active"
    curriculum: str | None = None
    total_hours: int | None = Field(default=None, ge=0)
    reported_done_hours: int | None = Field(default=None, ge=0)
    reported_at: date | None = None
    expected_end: str | None = None
    notes: str | None = None


class DegreeOut(DegreeIn, ORM):
    id: int


class DegreeComponentIn(BaseModel):
    degree_id: int
    name: str = Field(min_length=1, max_length=100)
    required_hours: int | None = Field(default=None, ge=0)
    done_hours: int = Field(default=0, ge=0)
    kind: Literal["subjects", "acc", "manual"] = "subjects"
    to_check: bool = False
    notes: str | None = None


class DegreeComponentOut(DegreeComponentIn, ORM):
    id: int


class SemesterIn(BaseModel):
    degree_id: int
    code: str = Field(min_length=1, max_length=20)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    notes: str | None = None


class SemesterOut(SemesterIn, ORM):
    id: int


SubjectStatus = Literal["pending", "in_progress", "passed", "failed"]


class SubjectIn(BaseModel):
    degree_id: int
    semester_id: int | None = None
    component_id: int | None = None
    name: str = Field(min_length=1, max_length=200)
    code: str | None = None
    hours: int | None = Field(default=None, ge=0)
    status: SubjectStatus = "pending"
    grading_rule: dict | None = None
    exam_requires_lab: bool = False
    notes: str | None = None

    @field_validator("grading_rule")
    @classmethod
    def _valid_rule(cls, v: dict | None) -> dict | None:
        # Garante que a regra gravada segue o formato do motor de avaliação
        if v is not None:
            GradingRule.model_validate(v)
        return v


class SubjectOut(SubjectIn, ORM):
    id: int


class PortalProgressIn(BaseModel):
    percent: float | None = Field(default=None, ge=0, le=100)
    contents_done: int | None = Field(default=None, ge=0)
    contents_total: int | None = Field(default=None, ge=0)
    exercises_done: int | None = Field(default=None, ge=0)
    exercises_total: int | None = Field(default=None, ge=0)
    mocks_done: int | None = Field(default=None, ge=0)
    mocks_total: int | None = Field(default=None, ge=0)
    lab_done: int | None = Field(default=None, ge=0)
    lab_total: int | None = Field(default=None, ge=0)
    as_of: date | None = None


class PortalProgressOut(PortalProgressIn, ORM):
    id: int
    subject_id: int


class TopicIn(BaseModel):
    subject_id: int
    position: int = 0
    title: str = Field(min_length=1, max_length=300)
    portal_done: bool = False
    learning_status: Literal["pending", "learned", "review"] = "pending"
    notion_page_id: str | None = None
    source_text: str | None = Field(default=None, max_length=30_000)  # mesmo limite do agente (MAX_TEXT)
    notes: str | None = None


class TopicOut(TopicIn, ORM):
    id: int


class ExamIn(BaseModel):
    subject_id: int
    kind: str = "AV"
    scheduled_at: datetime | None = None
    schedule_by: date | None = None
    location: str | None = None
    score: float | None = Field(default=None, ge=0)
    gcal_event_id: str | None = None
    notes: str | None = None


class ExamOut(ExamIn, ORM):
    id: int


class DeadlineIn(BaseModel):
    subject_id: int | None = None
    title: str = Field(min_length=1, max_length=300)
    due_date: date
    kind: Literal["deadline", "event"] = "deadline"
    gcal_event_id: str | None = None
    notes: str | None = None


class DeadlineOut(DeadlineIn, ORM):
    id: int


# --- ACC ---------------------------------------------------------------------


class AccActivityIn(BaseModel):
    degree_id: int
    title: str = Field(min_length=1, max_length=300)
    category: str | None = None
    hours: float = Field(gt=0)
    activity_date: date | None = None
    certificate_path: str | None = None
    status: Literal["registered", "planned"] = "registered"
    notes: str | None = None


class AccActivityOut(AccActivityIn, ORM):
    id: int


class AccRuleIn(BaseModel):
    degree_id: int
    category: str = Field(min_length=1, max_length=100)
    max_hours: int | None = Field(default=None, ge=0)
    max_hours_per_activity: int | None = Field(default=None, ge=0)
    notes: str | None = None


class AccRuleOut(AccRuleIn, ORM):
    id: int


# --- Configurações -----------------------------------------------------------


class SettingOut(ORM):
    key: str
    value: object


class SettingIn(BaseModel):
    value: object


# --- Sessões de estudo (cronômetro) ------------------------------------------


class StudySessionIn(BaseModel):
    subject_id: int | None = None
    topic_id: int | None = None
    started_at: datetime
    ended_at: datetime | None = None
    seconds: int = Field(ge=0, le=24 * 3600)
    notes: str | None = None


class StudySessionOut(StudySessionIn, ORM):
    id: int


# --- Registro de erros --------------------------------------------------------


class MistakeIn(BaseModel):
    question_id: int
    topic_id: int
    video_minute: str | None = Field(default=None, max_length=20)
    reviewed: bool = False
    notes: str | None = None


class MistakeOut(MistakeIn, ORM):
    id: int
