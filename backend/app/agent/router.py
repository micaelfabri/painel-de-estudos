"""Rotas do agente de estudos (SPEC §6.2, §7)."""

import random
from datetime import datetime
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import learning, models, settings_store
from ..integrations import notion
from ..db import get_session
from . import prompts
from .client import LLMClient, LLMError

router = APIRouter(prefix="/api/agent", tags=["agente"])

# Texto do tema enviado ao modelo: só conteúdo de estudo (nunca notas ou dados pessoais)
MAX_TEXT = 30_000


def get_client(request: Request, session: Session = Depends(get_session)) -> LLMClient:
    # Os testes trocam o transporte HTTP por um modelo falso em app.state.llm_transport
    return LLMClient(session, transport=getattr(request.app.state, "llm_transport", None))


def _llm_http_error(exc: LLMError) -> HTTPException:
    return HTTPException(422 if exc.status == "no_model" else 502, {"message": str(exc), "status": exc.status})


# --- Schemas das respostas do modelo -----------------------------------------


class GeneratedQuestion(BaseModel):
    statement: str = Field(min_length=3)
    options: list[str] = Field(min_length=2, max_length=6)
    correct_index: int
    explanation: str = ""

    @model_validator(mode="after")
    def _check(self):
        if not 0 <= self.correct_index < len(self.options):
            raise ValueError("correct_index fora das alternativas")
        if any(not o.strip() for o in self.options):
            raise ValueError("alternativa vazia")
        return self


class GeneratedSet(BaseModel):
    summary: str = Field(min_length=3)
    questions: list[GeneratedQuestion] = Field(min_length=1)


def set_schema(n_questions: int, n_options: int) -> type[GeneratedSet]:
    """Schema com as contagens exatas do pedido. Vai também como json_schema ao servidor, então o
    LM Studio já obriga o modelo a devolver N questões com N alternativas (F0: um modelo devolveu
    menos questões e outro, 4 alternativas quando pedimos 5)."""

    class Question(GeneratedQuestion):
        options: list[str] = Field(min_length=n_options, max_length=n_options)

    class Set(GeneratedSet):
        questions: list[Question] = Field(min_length=n_questions, max_length=n_questions)

    Set.__name__ = "GeneratedSet"
    return Set


def shuffle_options(q: GeneratedQuestion, rng: random.Random) -> tuple[list[str], int]:
    """Embaralha as alternativas: na F0 um modelo pôs a certa na letra A em 82% das questões."""
    order = list(range(len(q.options)))
    rng.shuffle(order)
    return [q.options[i].strip() for i in order], order.index(q.correct_index)


class ChatAnswer(BaseModel):
    answer: str = Field(min_length=1)


# --- Modelos -----------------------------------------------------------------


@router.get("/models")
def list_models(client: LLMClient = Depends(get_client), session: Session = Depends(get_session)):
    default = settings_store.get(session, "default_model")
    try:
        names = client.list_models()
        return {"base_url": client.base_url, "reachable": True, "models": names, "default_model": default, "error": None}
    except httpx.HTTPError as exc:
        return {"base_url": client.base_url, "reachable": False, "models": [], "default_model": default,
                "error": f"Modelo local fora do ar em {client.base_url}: {exc.__class__.__name__}"}
    except ValueError:
        # Respondeu, mas não é JSON (outro programa na porta?)
        return {"base_url": client.base_url, "reachable": False, "models": [], "default_model": default,
                "error": f"O endereço {client.base_url} respondeu, mas não parece uma API compatível com OpenAI"}


# --- Conjuntos de questões ---------------------------------------------------


class GenerateIn(BaseModel):
    topic_id: int
    text: str | None = Field(default=None, max_length=MAX_TEXT)
    model: str | None = None
    n_options: int = Field(ge=2, le=6)
    attempt_type: Literal["first", "retest_1d", "retest_7d", "retest_21d", "retest_3d"] = "first"

    @field_validator("text")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        return v.strip() if v and v.strip() else None


def _question_out(q: models.Question) -> dict:
    answered = q.answer is not None
    return {
        "id": q.id,
        "position": q.position,
        "statement": q.statement,
        "options": q.options,
        "flagged_bad": q.flagged_bad,
        # A correta e a explicação só aparecem depois de responder
        "answer": (
            {"chosen_index": q.answer.chosen_index, "is_correct": q.answer.is_correct,
             "correct_index": q.correct_index, "explanation": q.explanation}
            if answered else None
        ),
    }


def _set_out(qs: models.QuestionSet, topic: models.Topic) -> dict:
    return {
        "id": qs.id,
        "topic_id": qs.topic_id,
        "topic_title": topic.title,
        "subject_id": topic.subject_id,
        "attempt_type": qs.attempt_type,
        "model": qs.model,
        "prompt_version": qs.prompt_version,
        "summary": qs.summary,
        "score": qs.score,
        "completed_at": qs.completed_at.isoformat() if qs.completed_at else None,
        "created_at": qs.created_at.isoformat() if qs.created_at else None,
        "questions": [_question_out(q) for q in qs.questions],
    }


def _load_set(session: Session, set_id: int) -> models.QuestionSet:
    qs = session.scalars(
        select(models.QuestionSet)
        .where(models.QuestionSet.id == set_id)
        .options(selectinload(models.QuestionSet.questions).selectinload(models.Question.answer))
    ).first()
    if qs is None:
        raise HTTPException(404, "conjunto de questões não encontrado")
    return qs


@router.post("/question-sets", status_code=201)
def generate_question_set(data: GenerateIn, request: Request, session: Session = Depends(get_session),
                          client: LLMClient = Depends(get_client)):
    topic = session.get(models.Topic, data.topic_id)
    if topic is None:
        raise HTTPException(404, "tema não encontrado")
    if data.text:
        topic.source_text = data.text
        session.commit()
    text = topic.source_text
    if not text:
        raise HTTPException(422, {"message": "Cole o texto do tema antes de gerar as questões.", "status": "no_text"})

    subject = session.get(models.Subject, topic.subject_id)
    n_questions = int(settings_store.get(session, "questions_per_set"))
    prompt = prompts.load("generate_questions")
    # Retestes usam questões novas: as já feitas no tema vão como lista a evitar (prompt v2)
    previous = session.scalars(
        select(models.Question.statement)
        .join(models.QuestionSet)
        .where(models.QuestionSet.topic_id == topic.id)
        .order_by(models.Question.id.desc())
        .limit(40)
    ).all()
    avoid = "\n".join(f"- {s}" for s in previous) or "(nenhuma)"
    rendered = prompt.render(n_questions=n_questions, n_options=data.n_options, avoid=avoid,
                             topic_title=f"{subject.name if subject else ''} · {topic.title}", text=text)
    try:
        result, model_used = client.chat_json(prompt, rendered, set_schema(n_questions, data.n_options), data.model)
    except LLMError as exc:
        raise _llm_http_error(exc) from exc

    qs = models.QuestionSet(topic_id=topic.id, attempt_type=data.attempt_type, model=model_used,
                            prompt_version=f"{prompt.name}.{prompt.version}", summary=result.summary.strip())
    session.add(qs)
    session.flush()
    # Testes desligam o embaralhamento para saber onde está a certa
    rng = random.Random() if getattr(request.app.state, "shuffle_options", True) else None
    for i, q in enumerate(result.questions[:n_questions], start=1):
        options, correct = shuffle_options(q, rng) if rng else ([o.strip() for o in q.options], q.correct_index)
        session.add(models.Question(question_set_id=qs.id, position=i, statement=q.statement.strip(),
                                    options=options, correct_index=correct,
                                    explanation=q.explanation.strip() or None))
    session.commit()
    return _set_out(_load_set(session, qs.id), topic)


@router.get("/question-sets")
def list_question_sets(topic_id: int | None = None, session: Session = Depends(get_session)):
    stmt = select(models.QuestionSet).order_by(models.QuestionSet.created_at.desc())
    if topic_id is not None:
        stmt = stmt.where(models.QuestionSet.topic_id == topic_id)
    rows = session.scalars(stmt.limit(100)).all()
    return [{"id": r.id, "topic_id": r.topic_id, "attempt_type": r.attempt_type, "score": r.score,
             "completed_at": r.completed_at.isoformat() if r.completed_at else None, "model": r.model} for r in rows]


@router.get("/question-sets/{set_id}")
def get_question_set(set_id: int, session: Session = Depends(get_session)):
    qs = _load_set(session, set_id)
    return _set_out(qs, session.get(models.Topic, qs.topic_id))


def _recompute_score(session: Session, qs: models.QuestionSet) -> None:
    """Nota em 0..1 sem as questões marcadas como ruins; fecha o conjunto quando todas foram respondidas."""
    valid = [q for q in qs.questions if not q.flagged_bad]
    if valid and all(q.answer is not None for q in valid):
        qs.score = sum(1 for q in valid if q.answer.is_correct) / len(valid)
        first_close = qs.completed_at is None
        qs.completed_at = qs.completed_at or datetime.now()
        if first_close:
            learning.on_set_completed(session, qs)


class AnswerIn(BaseModel):
    chosen_index: int = Field(ge=0)


@router.post("/questions/{question_id}/answer")
def answer_question(question_id: int, data: AnswerIn, request: Request, session: Session = Depends(get_session)):
    q = session.get(models.Question, question_id)
    if q is None:
        raise HTTPException(404, "questão não encontrada")
    if q.answer is not None:
        raise HTTPException(409, "questão já respondida")
    if data.chosen_index >= len(q.options):
        raise HTTPException(422, "alternativa inexistente")
    correct = data.chosen_index == q.correct_index
    q.answer = models.Answer(chosen_index=data.chosen_index, is_correct=correct)
    qs = q.question_set
    mistake = None
    if not correct:
        mistake = models.Mistake(question_id=q.id, topic_id=qs.topic_id)
        session.add(mistake)
    session.flush()
    _recompute_score(session, qs)
    session.commit()
    notion_sync = None
    if qs.completed_at is not None:
        # F5: grava o resultado no fim da página do tema; se falhar, fica pendente para "Sincronizar"
        notion_sync = notion.sync_set(session, qs, notion.transport_of(request))
        session.commit()
    return {"is_correct": correct, "correct_index": q.correct_index, "explanation": q.explanation,
            "mistake_id": mistake.id if mistake else None,
            "set_score": qs.score, "set_completed": qs.completed_at is not None, "notion_sync": notion_sync}


@router.post("/questions/{question_id}/flag")
def flag_question(question_id: int, session: Session = Depends(get_session)):
    q = session.get(models.Question, question_id)
    if q is None:
        raise HTTPException(404, "questão não encontrada")
    q.flagged_bad = True
    qs = q.question_set
    session.flush()
    _recompute_score(session, qs)
    session.commit()
    return {"flagged_bad": True, "set_score": qs.score}


# --- Conversa ----------------------------------------------------------------


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    topic_id: int | None = None
    model: str | None = None
    history: list[ChatMessage] = Field(default_factory=list, max_length=12)


@router.post("/chat")
def chat(data: ChatIn, session: Session = Depends(get_session), client: LLMClient = Depends(get_client)):
    topic = session.get(models.Topic, data.topic_id) if data.topic_id else None
    prompt = prompts.load("chat")
    rendered = prompt.render(topic_title=topic.title if topic else "nenhum",
                             text=(topic.source_text or "(sem texto)") if topic else "(nenhum tema selecionado)")
    history = [m.model_dump() for m in data.history] + [{"role": "user", "content": data.message}]
    try:
        result, model_used = client.chat_json(prompt, rendered, ChatAnswer, data.model, history)
    except LLMError as exc:
        raise _llm_http_error(exc) from exc
    return {"answer": result.answer.strip(), "model": model_used}


# --- Registro de uso ---------------------------------------------------------


@router.get("/usage")
def usage(session: Session = Depends(get_session)):
    rows = session.scalars(select(models.LlmCall).order_by(models.LlmCall.id.desc()).limit(200)).all()
    return [
        {"id": r.id, "created_at": r.created_at.isoformat() if r.created_at else None, "model": r.model,
         "prompt": f"{r.prompt_name}.{r.prompt_version}", "input_tokens": r.input_tokens,
         "output_tokens": r.output_tokens, "latency_ms": r.latency_ms, "attempts": r.attempts,
         "status": r.status, "error": r.error}
        for r in rows
    ]
