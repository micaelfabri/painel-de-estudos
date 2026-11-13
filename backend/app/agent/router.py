"""Rotas do agente de estudos (SPEC §6.2, §7)."""

import random
from datetime import datetime
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import areas, learning, models, settings_store
from ..db import get_session
from ..integrations import notion
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


def set_title(qs: models.QuestionSet, topic: models.Topic | None, subject: models.Subject | None) -> str:
    """Título do conjunto: o tema; sem tema, simulado ou "erros" (refazer de vários temas)."""
    if topic:
        return topic.title
    base = "Erros para refazer" if qs.attempt_type == "redo" else "Simulado"
    return f"{base} · {subject.name}" if subject else base


def _set_out(qs: models.QuestionSet, topic: models.Topic | None, session: Session | None = None) -> dict:
    subject_id = topic.subject_id if topic else qs.subject_id
    subject = session.get(models.Subject, subject_id) if session and subject_id else None
    return {
        "id": qs.id,
        "topic_id": qs.topic_id,
        "topic_title": set_title(qs, topic, subject),
        "subject_id": subject_id,
        "time_limit_minutes": qs.time_limit_minutes,
        # Tempo que falta no simulado; created_at é hora local desde a v1.7
        "seconds_left": (max(0, int(qs.time_limit_minutes * 60 - (datetime.now() - qs.created_at).total_seconds()))
                         if qs.time_limit_minutes and qs.created_at and qs.completed_at is None else None),
        "label": learning.LABELS.get(qs.attempt_type, qs.attempt_type),
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
    return _set_out(_load_set(session, qs.id), topic, session)


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
    return _set_out(qs, session.get(models.Topic, qs.topic_id) if qs.topic_id else None, session)


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
    topic_id = q.topic_id or qs.topic_id
    if q.source_question_id is not None:
        # D28: cópia do refazer → atualiza o erro da questão original (corrigido ou revisar de novo)
        learning.record_retry(session, q, correct, topic_id)
    elif not correct and topic_id is not None:
        mistake = models.Mistake(question_id=q.id, topic_id=topic_id)
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


# --- v1.3: histórico, refazer erradas, testes de foco e simulado (D15, D16) ---


def _rng(request: Request) -> random.Random | None:
    # Testes desligam o embaralhamento para saber onde está a certa
    return random.Random() if getattr(request.app.state, "shuffle_options", True) else None


def _save_set(session: Session, request: Request, *, topic_id: int | None, subject_id: int | None,
              attempt_type: str, model: str, prompt_version: str, summary: str | None,
              questions: list[tuple[GeneratedQuestion, int | None]], source_set_id: int | None = None,
              time_limit_minutes: int | None = None,
              source_question_ids: list[int | None] | None = None) -> models.QuestionSet:
    qs = models.QuestionSet(topic_id=topic_id, subject_id=subject_id, attempt_type=attempt_type, model=model,
                            prompt_version=prompt_version, summary=summary, source_set_id=source_set_id,
                            time_limit_minutes=time_limit_minutes)
    session.add(qs)
    session.flush()
    rng = _rng(request)
    for i, (q, q_topic) in enumerate(questions, start=1):
        options, correct = shuffle_options(q, rng) if rng else ([o.strip() for o in q.options], q.correct_index)
        session.add(models.Question(question_set_id=qs.id, topic_id=q_topic, position=i,
                                    statement=q.statement.strip(), options=options, correct_index=correct,
                                    explanation=(q.explanation or "").strip() or None,
                                    source_question_id=source_question_ids[i - 1] if source_question_ids else None))
    session.commit()
    return _load_set(session, qs.id)


@router.post("/question-sets/{set_id}/redo", status_code=201)
def redo_wrong(set_id: int, request: Request, session: Session = Depends(get_session)):
    """Novo conjunto só com as questões erradas (ou não respondidas no tempo) de um conjunto. Sem modelo."""
    src = _load_set(session, set_id)
    wrong = [q for q in src.questions if not q.flagged_bad and q.answer is not None and not q.answer.is_correct]
    if not wrong:
        raise HTTPException(409, "Este conjunto não tem questões erradas para refazer.")
    copies = [_copy(q, q.topic_id or src.topic_id) for q in wrong]
    qs = _save_set(session, request, topic_id=src.topic_id, subject_id=src.subject_id, attempt_type="redo",
                   model="(sem modelo)", prompt_version="redo", summary=None, questions=copies,
                   source_set_id=src.id, source_question_ids=[q.source_question_id or q.id for q in wrong])
    return _set_out(qs, session.get(models.Topic, qs.topic_id) if qs.topic_id else None, session)


def _copy(q: models.Question, topic_id: int | None) -> tuple[GeneratedQuestion, int | None]:
    return (GeneratedQuestion(statement=q.statement, options=list(q.options), correct_index=q.correct_index,
                              explanation=q.explanation or ""), topic_id)


class MistakesRedoIn(BaseModel):
    subject_id: int | None = None
    topic_id: int | None = None
    # Padrão: tudo que não foi corrigido (não revisados, revisados e para revisar de novo)
    statuses: list[Literal["open", "reviewed", "again"]] = Field(default_factory=lambda: ["open", "reviewed", "again"])
    limit: int = Field(default=10, ge=1, le=50)
    # v1.8: refazer só os erros da área aberta (faculdade ou cursos); vazio = todos
    area: areas.Area | None = None


@router.post("/mistakes/redo", status_code=201)
def redo_mistakes(data: MistakesRedoIn, request: Request, session: Session = Depends(get_session)):
    """D28: novo conjunto com os erros ainda não corrigidos (de um tema, de uma disciplina ou de tudo). Sem modelo."""
    stmt = (select(models.Mistake).join(models.Topic, models.Topic.id == models.Mistake.topic_id)
            .where(models.Mistake.status.in_(data.statuses))
            .order_by(models.Mistake.updated_at, models.Mistake.id))
    if data.topic_id is not None:
        stmt = stmt.where(models.Mistake.topic_id == data.topic_id)
    if data.subject_id is not None:
        stmt = stmt.where(models.Topic.subject_id == data.subject_id)
    if data.area is not None and data.topic_id is None and data.subject_id is None:
        ids = areas.course_subject_ids(session)
        stmt = stmt.where(models.Topic.subject_id.in_(ids) if data.area == "cursos" else models.Topic.subject_id.not_in(ids))
    mistakes = session.scalars(stmt.limit(data.limit)).all()
    questions = [(m, session.get(models.Question, m.question_id)) for m in mistakes]
    questions = [(m, q) for m, q in questions if q is not None and not q.flagged_bad]
    if not questions:
        raise HTTPException(409, "Nenhum erro para refazer aqui.")
    topic_ids = {m.topic_id for m, _ in questions}
    subject_ids = {session.get(models.Topic, t).subject_id for t in topic_ids}
    qs = _save_set(session, request, topic_id=next(iter(topic_ids)) if len(topic_ids) == 1 else None,
                   subject_id=next(iter(subject_ids)) if len(subject_ids) == 1 else None, attempt_type="redo",
                   model="(sem modelo)", prompt_version="redo", summary=None,
                   questions=[_copy(q, m.topic_id) for m, q in questions],
                   source_question_ids=[q.id for _, q in questions])
    return _set_out(qs, session.get(models.Topic, qs.topic_id) if qs.topic_id else None, session)


@router.post("/question-sets/{set_id}/finish")
def finish_set(set_id: int, session: Session = Depends(get_session)):
    """Fecha o conjunto (tempo do simulado acabou ou desisti): as não respondidas contam como erradas."""
    qs = _load_set(session, set_id)
    if qs.completed_at is not None:
        return _set_out(qs, session.get(models.Topic, qs.topic_id) if qs.topic_id else None, session)
    for q in qs.questions:
        if q.answer is None and not q.flagged_bad:
            q.answer = models.Answer(chosen_index=-1, is_correct=False)
            topic_id = q.topic_id or qs.topic_id
            if q.source_question_id is not None:
                learning.record_retry(session, q, False, topic_id)
            elif topic_id is not None:
                session.add(models.Mistake(question_id=q.id, topic_id=topic_id))
    session.flush()
    _recompute_score(session, qs)
    session.commit()
    return _set_out(_load_set(session, set_id), session.get(models.Topic, qs.topic_id) if qs.topic_id else None,
                    session)


class FocusIn(BaseModel):
    topic_id: int
    focus: Literal["errors", "hits"]
    model: str | None = None
    n_options: int = Field(ge=2, le=6)


FOCUS_RULE = {
    "errors": "As questões de referência são as que o aluno ERROU. Faça questões novas que treinem exatamente "
              "esses pontos, para ele fixar o que ainda não sabe.",
    "hits": "As questões de referência são as que o aluno ACERTOU. Faça questões novas, um pouco mais difíceis, "
            "sobre esses mesmos pontos, para confirmar que ele sabe de verdade e não só decorou.",
}


@router.post("/question-sets/focus", status_code=201)
def generate_focused(data: FocusIn, request: Request, session: Session = Depends(get_session),
                     client: LLMClient = Depends(get_client)):
    topic = session.get(models.Topic, data.topic_id)
    if topic is None:
        raise HTTPException(404, "tema não encontrado")
    if not topic.source_text:
        raise HTTPException(422, {"message": "Este tema ainda não tem texto salvo. Gere um teste normal antes.",
                                  "status": "no_text"})
    rows = session.execute(
        select(models.Question)
        .join(models.QuestionSet, models.Question.question_set_id == models.QuestionSet.id)
        .join(models.Answer, models.Answer.question_id == models.Question.id)
        .where((models.Question.topic_id == topic.id) |
               ((models.Question.topic_id.is_(None)) & (models.QuestionSet.topic_id == topic.id)),
               models.Answer.is_correct.is_(data.focus == "hits"), models.Question.flagged_bad.is_(False))
        .order_by(models.Question.id.desc()).limit(15)
    ).scalars().all()
    if not rows:
        what = "erros" if data.focus == "errors" else "acertos"
        raise HTTPException(409, f"Ainda não há {what} neste tema para usar de base.")
    reference = "\n".join(f"- {q.statement} → certa: {q.options[q.correct_index]}" for q in rows)
    subject = session.get(models.Subject, topic.subject_id)
    n_questions = int(settings_store.get(session, "questions_per_set"))
    prompt = prompts.load("generate_focused")
    rendered = prompt.render(focus_rule=FOCUS_RULE[data.focus], n_questions=n_questions, n_options=data.n_options,
                             topic_title=f"{subject.name if subject else ''} · {topic.title}",
                             text=topic.source_text[:MAX_TEXT], reference=reference)
    try:
        result, model_used = client.chat_json(prompt, rendered, set_schema(n_questions, data.n_options), data.model)
    except LLMError as exc:
        raise _llm_http_error(exc) from exc
    qs = _save_set(session, request, topic_id=topic.id, subject_id=topic.subject_id,
                   attempt_type=f"focus_{data.focus}", model=model_used,
                   prompt_version=f"{prompt.name}.{prompt.version}", summary=result.summary.strip(),
                   questions=[(q, topic.id) for q in result.questions[:n_questions]])
    return _set_out(qs, topic, session)


class SimulationIn(BaseModel):
    subject_id: int
    model: str | None = None
    n_options: int = Field(ge=2, le=6)


class SimQuestion(GeneratedQuestion):
    topic_index: int = Field(ge=1)


def simulation_schema(n_questions: int, n_options: int) -> type[BaseModel]:
    class Question(SimQuestion):
        options: list[str] = Field(min_length=n_options, max_length=n_options)

    class Simulation(BaseModel):
        summary: str = Field(min_length=3)
        questions: list[Question] = Field(min_length=n_questions, max_length=n_questions)

    Simulation.__name__ = "GeneratedSimulation"
    return Simulation


@router.post("/simulations", status_code=201)
def generate_simulation(data: SimulationIn, request: Request, session: Session = Depends(get_session),
                        client: LLMClient = Depends(get_client)):
    subject = session.get(models.Subject, data.subject_id)
    if subject is None:
        raise HTTPException(404, "disciplina não encontrada")
    topics = session.scalars(select(models.Topic).where(models.Topic.subject_id == subject.id,
                                                        models.Topic.source_text.is_not(None))
                             .order_by(models.Topic.position)).all()
    topics = [t for t in topics if t.source_text and t.source_text.strip()]
    if not topics:
        raise HTTPException(422, {"message": "Nenhum tema desta disciplina tem texto salvo ainda. "
                                             "Gere pelo menos um teste de tema antes do simulado.",
                                  "status": "no_text"})
    # Cada tema leva uma fatia igual do limite de texto, para caber no contexto do modelo
    share = MAX_TEXT // len(topics)
    block = "\n\n".join(f"[{i}] {t.title}\n\"\"\"\n{t.source_text[:share]}\n\"\"\"" for i, t in enumerate(topics, 1))
    n_questions = int(settings_store.get(session, "questions_per_set"))
    prompt = prompts.load("generate_simulation")
    rendered = prompt.render(subject_name=subject.name, n_questions=n_questions, n_options=data.n_options,
                             topics=block)
    try:
        result, model_used = client.chat_json(prompt, rendered, simulation_schema(n_questions, data.n_options),
                                              data.model)
    except LLMError as exc:
        raise _llm_http_error(exc) from exc
    pairs = []
    for q in result.questions[:n_questions]:
        idx = q.topic_index if 1 <= q.topic_index <= len(topics) else None
        pairs.append((q, topics[idx - 1].id if idx else None))
    qs = _save_set(session, request, topic_id=None, subject_id=subject.id, attempt_type="simulation",
                   model=model_used, prompt_version=f"{prompt.name}.{prompt.version}",
                   summary=result.summary.strip(), questions=pairs,
                   time_limit_minutes=int(settings_store.get(session, "exam_minutes")))
    return _set_out(qs, None, session)


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
    # D25: números de estudo só vão ao modelo (local) se eu liberar em Configurações
    if settings_store.get(session, "agent_reads_metrics"):
        from .. import study

        metrics = study.metrics_text(session)
    else:
        metrics = "(acesso aos números não liberado em Configurações)"
    rendered = prompt.render(topic_title=topic.title if topic else "nenhum",
                             text=(topic.source_text or "(sem texto)") if topic else "(nenhum tema selecionado)",
                             metrics=metrics)
    # v1.5: a conversa fica salva; sem histórico enviado pela tela, usa as últimas mensagens salvas
    past = [m.model_dump() for m in data.history] or [
        {"role": m.role, "content": m.content} for m in reversed(session.scalars(
            select(models.ChatMessage).order_by(models.ChatMessage.id.desc()).limit(CHAT_CONTEXT)).all())]
    history = past + [{"role": "user", "content": data.message}]
    try:
        result, model_used = client.chat_json(prompt, rendered, ChatAnswer, data.model, history)
    except LLMError as exc:
        raise _llm_http_error(exc) from exc
    answer = result.answer.strip()
    session.add_all([
        models.ChatMessage(role="user", content=data.message, topic_id=data.topic_id),
        models.ChatMessage(role="assistant", content=answer, topic_id=data.topic_id, model=model_used),
    ])
    session.commit()
    return {"answer": answer, "model": model_used}


CHAT_CONTEXT = 10  # mensagens anteriores que vão de contexto ao modelo


@router.get("/chat/messages")
def chat_messages(limit: int = 60, session: Session = Depends(get_session)):
    rows = session.scalars(select(models.ChatMessage).order_by(models.ChatMessage.id.desc())
                           .limit(min(max(limit, 1), 500))).all()
    return [{"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()
             if m.created_at else None} for m in reversed(rows)]


@router.delete("/chat/messages", status_code=204)
def clear_chat(session: Session = Depends(get_session)):
    """Limpar conversa (com confirmação na tela). Só apaga a conversa; testes e notas continuam."""
    session.query(models.ChatMessage).delete()
    session.commit()


# --- Registro de uso ---------------------------------------------------------


@router.get("/usage")
def usage(page: int = Query(1, ge=1), per_page: int = Query(10, ge=1, le=100),
          session: Session = Depends(get_session)):
    """Registro de uso do modelo, paginado (v1.7; DS: 10 por página), mais recente primeiro."""
    total = session.scalar(select(func.count(models.LlmCall.id))) or 0
    pages = max(1, -(-total // per_page))
    page = min(page, pages)
    rows = session.scalars(select(models.LlmCall).order_by(models.LlmCall.id.desc())
                           .offset((page - 1) * per_page).limit(per_page)).all()
    return {
        "page": page, "pages": pages, "per_page": per_page, "total": total,
        "items": [
            {"id": r.id, "created_at": r.created_at.isoformat() if r.created_at else None, "model": r.model,
             "prompt": f"{r.prompt_name}.{r.prompt_version}", "input_tokens": r.input_tokens,
             "output_tokens": r.output_tokens, "latency_ms": r.latency_ms, "attempts": r.attempts,
             "status": r.status, "error": r.error}
            for r in rows
        ],
    }
