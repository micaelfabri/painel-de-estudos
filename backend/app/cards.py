"""Cards de estudo a partir dos meus pontos fracos (SPEC v1.6, D32–D37).

- Escolha (D32): erros "revisar de novo" > "não revisado" > tema em "Revisar" ou abaixo de 70% >
  erros "revisado"; empate vai para a disciplina com a prova mais próxima. Erro que já virou card
  não conta de novo.
- Dois jeitos de responder (D33): Responder (alternativas) e Virar (Sabia/Não sabia). O resultado
  muda o erro de origem no ciclo dos erros (D28).
- Repetição (D35): 1 → 7 → 21 → 60 dias; errar volta para 1 dia.
- Fontes (D34/D36): erros + texto e resumo do tema; prints (questão transcrita) e transcrições de
  vídeo da pasta de materiais. Tudo só no modelo local.
"""

import re
from datetime import date, datetime, timedelta
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import areas, learning, models
from .agent import prompts
from .agent.client import LLMClient, LLMError
from .agent.router import MAX_TEXT, _llm_http_error, get_client
from .db import get_session
from .integrations import notion, prints

router = APIRouter(prefix="/api/cards", tags=["cards"])

INTERVALS = [1, 7, 21, 60]  # dias (D35)
DEFAULT_CARDS = 10
FLIP_AFTER = 3  # acertos seguidos no Responder para o card passar a Virar (D33)
MAX_TRANSCRIPT = 30_000
KIND_LABELS = {"concept": "Conceito", "question": "Questão virada card", "confusion": "Confusão"}
SOURCE_LABELS = {"mistake": "Do erro", "text": "Do texto do tema", "print": "Do print", "video": "Do vídeo"}
MISTAKE_WEIGHT = {"again": 4, "open": 3, "reviewed": 1}


# --- Escolha dos pontos fracos (D32) -------------------------------------------


def _next_exam(session: Session, subject_id: int, today: date) -> date | None:
    rows = session.scalars(select(models.Exam).where(models.Exam.subject_id == subject_id,
                                                     models.Exam.done_at.is_(None))).all()
    days = [(e.scheduled_at.date() if e.scheduled_at else e.schedule_by) for e in rows]
    days = [d for d in days if d and d >= today]
    return min(days) if days else None


def _last_score(session: Session, topic_id: int) -> float | None:
    qs = session.scalars(select(models.QuestionSet).where(
        models.QuestionSet.topic_id == topic_id, models.QuestionSet.completed_at.is_not(None))
        .order_by(models.QuestionSet.completed_at.desc()).limit(1)).first()
    return qs.score if qs else None


def weak_topics(session: Session, today: date, subject_id: int | None = None,
                topic_id: int | None = None, area: areas.Area | None = None) -> list[dict]:
    """Temas em ordem de fraqueza, com os erros que ainda não viraram card."""
    covered = set(session.scalars(select(models.Card.mistake_id).where(models.Card.mistake_id.is_not(None))).all())
    stmt = select(models.Topic)
    if topic_id is not None:
        stmt = stmt.where(models.Topic.id == topic_id)
    elif subject_id is not None:
        stmt = stmt.where(models.Topic.subject_id == subject_id)
    out = []
    exams: dict[int, date | None] = {}
    course_ids = areas.course_subject_ids(session)
    for t in session.scalars(stmt).all():
        if topic_id is None and not areas.in_area(t.subject_id, area, course_ids):
            continue
        mistakes = session.scalars(select(models.Mistake).where(
            models.Mistake.topic_id == t.id, models.Mistake.status.in_(learning.UNFIXED))).all()
        open_ = [m for m in mistakes if m.id not in covered]
        last = _last_score(session, t.id)
        threshold = 0.7
        weak_topic = t.learning_status == "review" or (last is not None and last < threshold)
        weight = sum(MISTAKE_WEIGHT.get(m.status, 1) for m in open_) + (2 if weak_topic else 0)
        if t.subject_id not in exams:
            exams[t.subject_id] = _next_exam(session, t.subject_id, today)
        has_material = bool(t.source_text) or bool(open_)
        if topic_id is None and not has_material:
            continue
        open_.sort(key=lambda m: -MISTAKE_WEIGHT.get(m.status, 1))
        out.append({"topic": t, "weight": weight, "mistakes": open_, "exam": exams[t.subject_id], "last": last})
    far = date.max
    # Sem erro nem tema fraco (peso 0), ainda vale gerar do texto: primeiro a nota mais baixa e a prova mais perto
    out.sort(key=lambda x: (-x["weight"], x["exam"] or far, x["last"] if x["last"] is not None else 2.0))
    return out


# --- Geração (D34, D36) ----------------------------------------------------------


class GeneratedCard(BaseModel):
    kind: Literal["concept", "question", "confusion"]
    front: str = Field(min_length=3)
    back: str = Field(min_length=1)
    explanation: str = ""
    options: list[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    mistake: int | None = None
    video_minute: str | None = None

    @model_validator(mode="after")
    def _check(self):
        if any(not o.strip() for o in self.options):
            raise ValueError("alternativa vazia")
        if self.video_minute and not re.fullmatch(r"\d{1,3}:\d{2}", self.video_minute.strip()):
            self.video_minute = None
        return self


def cards_schema(n: int) -> type[BaseModel]:
    class GeneratedCards(BaseModel):
        cards: list[GeneratedCard] = Field(min_length=1, max_length=n)

    return GeneratedCards


def _mistake_lines(session: Session, mistakes: list[models.Mistake]) -> tuple[str, list[dict]]:
    lines, refs = [], []
    for m in mistakes:
        q = session.get(models.Question, m.question_id)
        if q is None:
            continue
        chosen = q.answer.chosen_index if q.answer else None
        picked = q.options[chosen] if chosen is not None and 0 <= chosen < len(q.options) else "não respondeu"
        refs.append({"mistake": m, "question": q, "picked": None if chosen is None or chosen < 0 else picked})
        lines.append(f"{len(refs)}. {q.statement} → certa: {q.options[q.correct_index]} · ele marcou: {picked}"
                     + (f" · explicação: {q.explanation}" if q.explanation else ""))
    return ("\n".join(lines) or "(nenhum erro registrado neste tema)"), refs


def _summary(session: Session, topic_id: int) -> str | None:
    return session.scalars(select(models.QuestionSet.summary).where(
        models.QuestionSet.topic_id == topic_id, models.QuestionSet.summary.is_not(None))
        .order_by(models.QuestionSet.id.desc()).limit(1)).first()


def _new_card(today: date, **kw) -> models.Card:
    return models.Card(step=0, next_review=today, answer_streak=0, mode="answer", **kw)


def generate_for_topic(session: Session, client: LLMClient, topic: models.Topic, mistakes: list[models.Mistake],
                       n: int, model: str | None, today: date, transcript: str | None = None,
                       transcript_label: str | None = None) -> list[models.Card]:
    if not topic.source_text and not mistakes and not transcript:
        raise HTTPException(409, "Este tema ainda não tem texto salvo nem erros para virar card.")
    mistake_text, refs = _mistake_lines(session, mistakes[:n])
    material = []
    if transcript:
        material.append(f"TRECHOS DE VÍDEO ({transcript_label}):\n{transcript[:MAX_TRANSCRIPT]}")
    if topic.source_text:
        material.append(f"TEXTO DO TEMA:\n{topic.source_text[:MAX_TEXT]}")
    if summary := _summary(session, topic.id):
        material.append(f"RESUMO:\n{summary}")
    subject = session.get(models.Subject, topic.subject_id)
    prompt = prompts.load("generate_cards")
    rendered = prompt.render(n_cards=n, topic_title=f"{subject.name if subject else ''} · {topic.title}",
                             material="\n\n".join(material) or "(sem texto; use só os erros)", mistakes=mistake_text)
    try:
        result, _ = client.chat_json(prompt, rendered, cards_schema(n), model)
    except LLMError as exc:
        raise _llm_http_error(exc) from exc

    existing = {c.front.strip().lower() for c in session.scalars(
        select(models.Card).where(models.Card.topic_id == topic.id)).all()}
    used: set[int] = set()
    created = []
    for g in result.cards[:n]:
        ref = refs[g.mistake - 1] if g.mistake and 1 <= g.mistake <= len(refs) else None
        if ref and ref["mistake"].id in used:
            ref = None  # nunca dois cards do mesmo erro (D32)
        if g.front.strip().lower() in existing:
            continue
        source = "mistake" if ref else ("video" if transcript and g.video_minute else "text")
        card = _new_card(
            today, topic_id=topic.id, kind=g.kind if ref or g.kind != "question" else "concept",
            front=g.front.strip(), back=g.back.strip(), explanation=g.explanation.strip() or None,
            options=[o.strip() for o in g.options], correct_index=g.correct_index, source=source,
            mistake_id=ref["mistake"].id if ref else None, chosen_text=ref["picked"] if ref else None,
            video_minute=(g.video_minute or (ref["mistake"].video_minute if ref else None)),
            source_label=transcript_label if source == "video" else None,
            prompt_version=f"{prompt.name}.{prompt.version}")
        if ref:
            used.add(ref["mistake"].id)
            card.kind = "question" if g.kind == "concept" else g.kind
        existing.add(card.front.lower())
        session.add(card)
        created.append(card)
    session.commit()
    return created


# --- Saída e revisão -------------------------------------------------------------


def card_out(session: Session, c: models.Card, today: date | None = None) -> dict:
    topic = session.get(models.Topic, c.topic_id)
    subject = session.get(models.Subject, topic.subject_id) if topic else None
    mistake = session.get(models.Mistake, c.mistake_id) if c.mistake_id else None
    today = today or date.today()
    return {
        "id": c.id, "topic_id": c.topic_id, "topic_title": topic.title if topic else "",
        "subject_id": subject.id if subject else None, "subject_name": subject.name if subject else "",
        "kind": c.kind, "kind_label": KIND_LABELS.get(c.kind, c.kind), "mode": c.mode,
        "front": c.front, "back": c.back, "explanation": c.explanation,
        "options": c.options, "correct_index": c.correct_index,
        "source": c.source, "source_label": SOURCE_LABELS.get(c.source, c.source), "source_detail": c.source_label,
        "mistake_id": c.mistake_id, "mistake_status": mistake.status if mistake else None,
        "chosen_text": c.chosen_text, "video_minute": c.video_minute,
        "notion_url": (f"https://www.notion.so/{topic.notion_page_id.replace('-', '')}"
                       if topic and topic.notion_page_id else None),
        "step": c.step, "next_review": c.next_review.isoformat(), "due": c.next_review <= today,
    }


def apply_review(session: Session, card: models.Card, mode: str, knew: bool, today: date) -> None:
    """Calendário (D35), troca Responder → Virar (D33) e efeito no erro de origem (D33/D28)."""
    if knew:
        card.next_review = today + timedelta(days=INTERVALS[min(card.step, len(INTERVALS) - 1)])
        card.step = min(card.step + 1, len(INTERVALS) - 1)
    else:
        card.step = 0
        card.next_review = today + timedelta(days=1)
    if mode == "answer":
        card.answer_streak = card.answer_streak + 1 if knew else 0
        if card.answer_streak >= FLIP_AFTER:
            card.mode = "flip"
    mistake = session.get(models.Mistake, card.mistake_id) if card.mistake_id else None
    if mistake is not None:
        if not knew:
            mistake.status = "again"
            mistake.reviewed = True
        elif mode == "answer":
            mistake.status = "fixed"
            mistake.reviewed = True
        elif mistake.status == "open":
            mistake.status = "reviewed"
            mistake.reviewed = True


class ReviewIn(BaseModel):
    mode: Literal["flip", "answer"]
    knew: bool | None = None
    chosen_index: int | None = Field(default=None, ge=0, le=9)

    @model_validator(mode="after")
    def _check(self):
        if self.mode == "flip" and self.knew is None:
            raise ValueError("no Virar, diga se sabia")
        if self.mode == "answer" and self.chosen_index is None:
            raise ValueError("no Responder, escolha uma alternativa")
        return self


@router.post("/{card_id}/review")
def review(card_id: int, data: ReviewIn, today: date | None = Query(None, description="Só para testes"),
           session: Session = Depends(get_session)):
    card = session.get(models.Card, card_id)
    if card is None:
        raise HTTPException(404, "card não encontrado")
    today = today or date.today()
    if data.mode == "answer":
        if not card.options or card.correct_index is None:
            raise HTTPException(422, "Este card não tem alternativas; use Virar.")
        knew = data.chosen_index == card.correct_index
    else:
        knew = bool(data.knew)
    apply_review(session, card, data.mode, knew, today)
    session.add(models.CardReview(card_id=card.id, mode=data.mode, knew=knew, chosen_index=data.chosen_index))
    session.commit()
    return {"knew": knew, "correct_index": card.correct_index, "card": card_out(session, card, today)}


# --- Endpoints ---------------------------------------------------------------------


class GenerateIn(BaseModel):
    scope: Literal["weak", "subject", "topic"] = "weak"
    area: areas.Area = "faculdade"
    subject_id: int | None = None
    topic_id: int | None = None
    n: int = Field(default=DEFAULT_CARDS, ge=3, le=20)
    model: str | None = None


@router.post("/generate", status_code=201)
def generate(data: GenerateIn, today: date | None = Query(None), session: Session = Depends(get_session),
             client: LLMClient = Depends(get_client)):
    """Gera cards do tema mais fraco (de tudo, da disciplina) ou de um tema escolhido (D34)."""
    today = today or date.today()
    if data.scope == "topic" and data.topic_id is None:
        raise HTTPException(422, "Escolha o tema.")
    if data.scope == "subject" and data.subject_id is None:
        raise HTTPException(422, "Escolha a disciplina.")
    ranked = weak_topics(session, today, subject_id=data.subject_id if data.scope == "subject" else None,
                         topic_id=data.topic_id if data.scope == "topic" else None, area=data.area)
    if not ranked:
        raise HTTPException(409, "Nenhum ponto fraco com material para virar card. Faça um teste antes.")
    first = ranked[0]
    if session.get(models.Topic, first["topic"].id) is None:
        raise HTTPException(404, "tema não encontrado")
    created = generate_for_topic(session, client, first["topic"], first["mistakes"], data.n, data.model, today)
    return {"topic_id": first["topic"].id, "topic_title": first["topic"].title,
            "cards": [card_out(session, c, today) for c in created]}


@router.get("")
def list_cards(topic_id: int | None = None, subject_id: int | None = None, due: bool = False,
               limit: int = Query(50, ge=1, le=500), today: date | None = Query(None),
               area: areas.Area | None = None, session: Session = Depends(get_session)):
    today = today or date.today()
    stmt = select(models.Card).join(models.Topic, models.Topic.id == models.Card.topic_id)
    if topic_id is not None:
        stmt = stmt.where(models.Card.topic_id == topic_id)
    if subject_id is not None:
        stmt = stmt.where(models.Topic.subject_id == subject_id)
    if due:
        stmt = stmt.where(models.Card.next_review <= today)
    if area is not None:
        ids = areas.course_subject_ids(session)
        stmt = stmt.where(models.Topic.subject_id.in_(ids) if area == "cursos" else models.Topic.subject_id.not_in(ids))
    rows = session.scalars(stmt.order_by(models.Card.next_review, models.Card.step, models.Card.id).limit(limit)).all()
    return [card_out(session, c, today) for c in rows]


@router.get("/summary")
def summary(today: date | None = Query(None), area: areas.Area | None = "faculdade",
            session: Session = Depends(get_session)):
    """Uma linha por tema: total de cards, vencidos hoje e quantos acertei na última revisão."""
    today = today or date.today()
    out = []
    by_topic: dict[int, dict] = {}
    course_ids = areas.course_subject_ids(session)
    topic_subject = areas.topic_subjects(session)
    for c in session.scalars(select(models.Card)).all():
        if not areas.in_area(topic_subject.get(c.topic_id), area, course_ids):
            continue
        row = by_topic.setdefault(c.topic_id, {"total": 0, "due": 0})
        row["total"] += 1
        row["due"] += 1 if c.next_review <= today else 0
    for topic_id, row in by_topic.items():
        topic = session.get(models.Topic, topic_id)
        subject = session.get(models.Subject, topic.subject_id)
        reviews = session.execute(select(models.CardReview.knew).join(models.Card).where(
            models.Card.topic_id == topic_id)).scalars().all()
        out.append({"topic_id": topic_id, "topic_title": topic.title, "subject_id": subject.id,
                    "subject_name": subject.name, **row, "reviews": len(reviews), "knew": sum(1 for k in reviews if k),
                    "has_notion": bool(topic.notion_page_id)})
    out.sort(key=lambda r: (-r["due"], r["subject_name"], r["topic_title"]))
    return {"due": sum(r["due"] for r in out), "total": sum(r["total"] for r in out), "topics": out}


class RoundIn(BaseModel):
    subject_id: int | None = None
    area: areas.Area = "faculdade"
    size: int = Field(default=10, ge=3, le=30)


@router.post("/round")
def quick_round(data: RoundIn, today: date | None = Query(None), session: Session = Depends(get_session)):
    """Rodada rápida (D37): até 10 cards dos pontos fracos, vencidos primeiro."""
    today = today or date.today()
    stmt = select(models.Card).join(models.Topic, models.Topic.id == models.Card.topic_id)
    if data.subject_id is not None:
        stmt = stmt.where(models.Topic.subject_id == data.subject_id)
    ids = areas.course_subject_ids(session)
    stmt = stmt.where(models.Topic.subject_id.in_(ids) if data.area == "cursos" else models.Topic.subject_id.not_in(ids))
    cards = session.scalars(stmt).all()
    if not cards:
        raise HTTPException(409, "Ainda não há cards. Gere cards antes.")

    def weight(c: models.Card) -> tuple:
        mistake = session.get(models.Mistake, c.mistake_id) if c.mistake_id else None
        return (c.next_review > today, -MISTAKE_WEIGHT.get(mistake.status if mistake else "", 0), c.step,
                c.next_review, c.id)

    cards.sort(key=weight)
    return [card_out(session, c, today) for c in cards[:data.size]]


def card_of_day(session: Session, today: date) -> models.Card | None:
    """Card do dia (D37): ponto mais fraco da disciplina com a prova mais próxima; fica o mesmo o dia todo."""
    chosen = session.scalars(select(models.Card).where(models.Card.day_card_on == today)).first()
    if chosen:
        return chosen
    # Card do dia vem da faculdade (fica no Painel)
    ids = areas.course_subject_ids(session)
    cards = session.scalars(select(models.Card).join(models.Topic, models.Topic.id == models.Card.topic_id)
                            .where(models.Topic.subject_id.not_in(ids))).all()
    if not cards:
        return None
    exams: dict[int, date | None] = {}

    def key(c: models.Card) -> tuple:
        topic = session.get(models.Topic, c.topic_id)
        if topic.subject_id not in exams:
            exams[topic.subject_id] = _next_exam(session, topic.subject_id, today)
        mistake = session.get(models.Mistake, c.mistake_id) if c.mistake_id else None
        return (exams[topic.subject_id] or date.max, c.next_review > today,
                -MISTAKE_WEIGHT.get(mistake.status if mistake else "", 0), c.step, c.id)

    best = min(cards, key=key)
    best.day_card_on = today
    session.commit()
    return best


@router.get("/today")
def today_card(today: date | None = Query(None), session: Session = Depends(get_session)):
    today = today or date.today()
    card = card_of_day(session, today)
    if card is None:
        return {"card": None, "answered": False}
    answered = session.scalars(select(models.CardReview).where(
        models.CardReview.card_id == card.id,
        models.CardReview.created_at >= datetime.combine(today, datetime.min.time()))).first() is not None
    return {"card": card_out(session, card, today), "answered": answered}


# --- Prints (C2, D36) ------------------------------------------------------------


class PrintCard(BaseModel):
    result: Literal["correct", "wrong", "unknown"]
    statement: str = ""
    options: list[str] = Field(default_factory=list, max_length=8)
    correct_index: int | None = Field(default=None, ge=0, le=7)
    chosen_index: int | None = Field(default=None, ge=0, le=7)
    explanation: str = ""


class FromPrintsIn(BaseModel):
    topic_id: int
    source: Literal["notion", "folder"]
    deadline_id: int | None = None  # página própria do item (lab, simulado) no Notion
    page_topic_id: int | None = None  # página de outro tema; padrão = o próprio tema
    section: str | None = Field(default=None, max_length=200)
    paths: list[str] = Field(default_factory=list, max_length=50)
    include_right: bool = False
    model: str | None = None


@router.post("/from-prints", status_code=201)
def from_prints(data: FromPrintsIn, request: Request, today: date | None = Query(None),
                session: Session = Depends(get_session)):
    """Lê os prints, transcreve as questões erradas e transforma cada uma num card (autorizado em 12/11/2026)."""
    today = today or date.today()
    topic = session.get(models.Topic, data.topic_id)
    if topic is None:
        raise HTTPException(404, "tema não encontrado")
    page_topic = data.page_topic_id or (None if data.deadline_id else data.topic_id)
    sources = prints.collect_sources(request, session, data.source, page_topic, data.deadline_id, data.section,
                                     data.paths)
    client = prints._client(request, session)
    model = prints._vision_model(session, data.model)
    image_transport = getattr(request.app.state, "image_transport", None)
    prompt = prompts.load("read_print_card")
    existing = {c.front.strip().lower() for c in session.scalars(
        select(models.Card).where(models.Card.topic_id == topic.id)).all()}
    created, skipped = [], []
    for src in sources:
        try:
            raw = src["raw"] if "raw" in src else prints.download(src["url"], image_transport)
            message = {"role": "user", "content": [
                {"type": "text", "text": "Este é o print. Responda só com o JSON pedido."},
                {"type": "image_url", "image_url": {"url": prints.to_data_url(raw)}},
            ]}
            reading, _ = client.chat_json(prompt, prompt.render(), PrintCard, model, [message])
        except LLMError as exc:
            if exc.status in ("no_model", "error") and not created and not skipped:
                raise _llm_http_error(exc) from exc
            skipped.append({"label": src["label"], "reason": f"o modelo não conseguiu ler: {exc}"[:200]})
            continue
        except (ValueError, httpx.HTTPError) as exc:
            skipped.append({"label": src["label"], "reason": f"imagem não lida: {exc}"[:200]})
            continue
        wanted = reading.result == "wrong" or (data.include_right and reading.result == "correct")
        usable = (reading.statement.strip() and len(reading.options) >= 2 and reading.correct_index is not None
                  and reading.correct_index < len(reading.options))
        if not wanted or not usable:
            reason = "acertou (não vira card)" if reading.result == "correct" else "não deu para ler a questão inteira"
            skipped.append({"label": src["label"], "reason": reason})
            continue
        front = reading.statement.strip()
        if front.lower() in existing:
            skipped.append({"label": src["label"], "reason": "já existe um card com essa questão"})
            continue
        options = [o.strip() for o in reading.options]
        chosen = (options[reading.chosen_index] if reading.chosen_index is not None
                  and reading.chosen_index < len(options) else None)
        card = _new_card(today, topic_id=topic.id, kind="question", front=front,
                         back=options[reading.correct_index], explanation=reading.explanation.strip() or None,
                         options=options, correct_index=reading.correct_index, source="print",
                         source_label=src["label"][:300], chosen_text=chosen,
                         prompt_version=f"{prompt.name}.{prompt.version}")
        existing.add(front.lower())
        session.add(card)
        created.append(card)
    session.commit()
    return {"images": len(sources), "cards": [card_out(session, c, today) for c in created], "skipped": skipped}


# --- Transcrições de vídeo (C4, D36) -------------------------------------------------

_TS = re.compile(r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})[.,]\d{1,3}\s*-->")


def parse_transcript(text: str, suffix: str) -> str:
    """VTT/SRT viram linhas "[mm:ss] fala"; TXT vai como está (pode já ter [mm:ss])."""
    if suffix not in (".vtt", ".srt"):
        return text.strip()
    out, current = [], None
    for line in text.splitlines():
        line = line.strip()
        m = _TS.search(line)
        if m:
            h, mi, se = int(m.group(1) or 0), int(m.group(2)), int(m.group(3))
            current = f"{h * 60 + mi:02d}:{se:02d}"
            continue
        if not line or line.isdigit() or line.upper().startswith("WEBVTT") or current is None:
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if out and out[-1].startswith(f"[{current}]"):
            out[-1] += " " + line
        else:
            out.append(f"[{current}] {line}")
    return "\n".join(out)


class FromTranscriptIn(BaseModel):
    topic_id: int
    path: str | None = Field(default=None, max_length=500)  # arquivo .vtt/.srt/.txt na pasta de materiais
    text: str | None = Field(default=None, max_length=MAX_TRANSCRIPT)  # ou a transcrição colada
    n: int = Field(default=DEFAULT_CARDS, ge=3, le=20)
    model: str | None = None


@router.post("/from-transcript", status_code=201)
def from_transcript(data: FromTranscriptIn, today: date | None = Query(None), session: Session = Depends(get_session),
                    client: LLMClient = Depends(get_client)):
    """Cards a partir da transcrição de um vídeo, citando o minuto (D36). A transcrição do áudio em si
    ainda não é feita pelo painel (fases de voz); aqui entra o arquivo de legenda/transcrição."""
    today = today or date.today()
    topic = session.get(models.Topic, data.topic_id)
    if topic is None:
        raise HTTPException(404, "tema não encontrado")
    if data.path:
        target = prints.safe_path(data.path)
        if not target.is_file() or target.suffix.lower() not in prints.TRANSCRIPT_EXT:
            raise HTTPException(404, "Escolha um arquivo .vtt, .srt ou .txt da pasta de materiais.")
        if target.stat().st_size > 2 * 1024 * 1024:
            raise HTTPException(413, "Transcrição passa de 2 MB.")
        text = parse_transcript(target.read_text(encoding="utf-8", errors="replace"), target.suffix.lower())
        label = target.name
    elif data.text and data.text.strip():
        text, label = parse_transcript(data.text, ".vtt" if "-->" in data.text else ".txt"), "transcrição colada"
    else:
        raise HTTPException(422, "Escolha o arquivo da transcrição ou cole o texto.")
    if not text:
        raise HTTPException(409, "A transcrição está vazia.")
    mistakes = next((r["mistakes"] for r in weak_topics(session, today, topic_id=topic.id)), [])
    created = generate_for_topic(session, client, topic, mistakes, data.n, data.model, today,
                                 transcript=text, transcript_label=label)
    return {"cards": [card_out(session, c, today) for c in created]}


# --- Notion (opcional, D37) ----------------------------------------------------------


@router.post("/topics/{topic_id}/notion")
def export_notion(topic_id: int, request: Request, session: Session = Depends(get_session)):
    """Acrescenta no fim da página do tema os cards ainda não enviados. Nunca apaga nada."""
    topic = session.get(models.Topic, topic_id)
    if topic is None:
        raise HTTPException(404, "tema não encontrado")
    if not topic.notion_page_id:
        raise HTTPException(409, "Este tema ainda não tem página do Notion ligada.")
    cards = session.scalars(select(models.Card).where(models.Card.topic_id == topic_id,
                                                      models.Card.notion_synced_at.is_(None))).all()
    if not cards:
        return {"sent": 0}
    text = notion._text
    blocks = [{"object": "block", "type": "heading_3", "heading_3": {"rich_text": text(
        f"Painel de Estudos · cards · {date.today().strftime('%d/%m/%Y')}")}}]
    for c in cards:
        extra = f" (vídeo {c.video_minute})" if c.video_minute else ""
        blocks.append({"object": "block", "type": "toggle", "toggle": {
            "rich_text": text(c.front),
            "children": [{"object": "block", "type": "paragraph",
                          "paragraph": {"rich_text": text(f"{c.back}{extra}" + (f" — {c.explanation}"
                                                                                  if c.explanation else ""))}}],
        }})
    try:
        client = notion.NotionClient(notion.transport_of(request), notion.sleep_of(request))
        for i in range(0, len(blocks), 90):  # o Notion aceita até 100 blocos por chamada
            client.append(topic.notion_page_id, blocks[i:i + 90])
    except notion.NotionError as exc:
        raise HTTPException(502, str(exc)) from exc
    now = datetime.now()
    for c in cards:
        c.notion_synced_at = now
    session.commit()
    return {"sent": len(cards)}


def due_count(session: Session, today: date, area: areas.Area | None = None) -> int:
    stmt = select(func.count(models.Card.id)).where(models.Card.next_review <= today)
    if area is not None:
        ids = areas.course_subject_ids(session)
        stmt = stmt.join(models.Topic, models.Topic.id == models.Card.topic_id).where(
            models.Topic.subject_id.in_(ids) if area == "cursos" else models.Topic.subject_id.not_in(ids))
    return session.scalar(stmt) or 0
