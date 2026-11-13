"""Notas pelos prints (SPEC D17, D18).

O agente lê os prints das minhas respostas (atividades, laboratórios, provas) e propõe
acertos, erros e nota. Nada é salvo aqui: a confirmação grava pelo lado Estudo.

Fontes permitidas, e só elas:
- imagens de uma página do Notion ligada a um tema;
- arquivos da pasta de materiais do curso, montada só para leitura em /app/materiais.

Regra de contagem (D17): print só da resposta certa = acerto de primeira; cada print com
resposta errada = uma tentativa errada. Nota = acertos de primeira ÷ total × 10.
Os prints vão só para o modelo local, nunca para a nuvem.
"""

import base64
import io
import logging
import os
from pathlib import Path
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models, settings_store
from ..agent import prompts
from ..agent.client import LLMClient, LLMError
from ..db import get_session
from . import notion

log = logging.getLogger("painel.prints")

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
PDF_EXT = {".pdf"}
TRANSCRIPT_EXT = {".vtt", ".srt", ".txt"}  # v1.6 (D36): transcrições de vídeo para cards
MAX_IMAGES = 40  # por análise: cada print é uma chamada ao modelo local
MAX_BYTES = 15 * 1024 * 1024
MAX_PDF_PAGES = 30
MAX_SIDE = 1280  # lado maior da imagem enviada ao modelo (menos tokens, texto ainda legível)


def materials_dir() -> Path:
    return Path(os.environ.get("PAINEL_MATERIALS_DIR", "/app/materiais"))


def safe_path(rel: str) -> Path:
    """Caminho dentro da pasta de materiais; qualquer coisa fora dela é recusada (D18)."""
    root = materials_dir().resolve()
    target = (root / rel.strip().lstrip("/\\")).resolve()
    if target != root and root not in target.parents:
        raise HTTPException(400, "Caminho fora da pasta de materiais.")
    return target


# --- Imagens -----------------------------------------------------------------


def to_data_url(raw: bytes) -> str:
    """Abre qualquer imagem, reduz para no máximo 1280 px e devolve um data URL JPEG."""
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("arquivo não é uma imagem válida") from exc
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def pdf_pages(path: Path) -> list[bytes]:
    import pypdfium2 as pdfium

    pages: list[bytes] = []
    doc = pdfium.PdfDocument(str(path))
    try:
        for i in range(min(len(doc), MAX_PDF_PAGES)):
            bitmap = doc[i].render(scale=150 / 72)
            buf = io.BytesIO()
            bitmap.to_pil().save(buf, format="PNG")
            pages.append(buf.getvalue())
    finally:
        doc.close()
    return pages


def folder_images(paths: list[str]) -> list[dict]:
    """Imagens dos arquivos escolhidos na pasta (PDF vira uma imagem por página)."""
    out: list[dict] = []
    for rel in paths:
        target = safe_path(rel)
        if target.is_dir():
            files = sorted(f for f in target.iterdir()
                           if f.is_file() and not f.name.startswith(".") and f.suffix.lower() in IMAGE_EXT | PDF_EXT)
        elif target.is_file():
            files = [target]
        else:
            raise HTTPException(404, f"Não encontrei {rel} na pasta de materiais.")
        root = materials_dir().resolve()
        for f in files:
            label = str(f.relative_to(root))
            if f.stat().st_size > MAX_BYTES:
                raise HTTPException(413, f"{label} passa de 15 MB.")
            if f.suffix.lower() in PDF_EXT:
                for n, page in enumerate(pdf_pages(f), start=1):
                    out.append({"label": f"{label} · página {n}", "raw": page})
            elif f.suffix.lower() in IMAGE_EXT:
                out.append({"label": label, "raw": f.read_bytes()})
    return out


def download(url: str, transport: httpx.BaseTransport | None = None) -> bytes:
    """Baixa a imagem do Notion (link temporário). Sem o token do Notion: o link já é assinado."""
    if not url.startswith("https://"):
        raise ValueError("link de imagem que não é https")
    with httpx.Client(timeout=httpx.Timeout(20.0), transport=transport, follow_redirects=False) as http:
        res = http.get(url)
    if res.status_code != 200:
        raise ValueError(f"imagem do Notion respondeu {res.status_code}")
    if len(res.content) > MAX_BYTES:
        raise ValueError("imagem do Notion passa de 15 MB")
    return res.content


# --- Leitura pelo modelo -----------------------------------------------------


class PrintReading(BaseModel):
    question_number: int | None = Field(default=None, ge=1, le=500)
    result: Literal["correct", "wrong", "unknown"]
    note: str = ""


class NumberReading(BaseModel):
    number: int


def read_image(client: LLMClient, data_url: str, model: str | None) -> PrintReading:
    prompt = prompts.load("read_print")
    message = {"role": "user", "content": [
        {"type": "text", "text": "Este é o print. Responda só com o JSON pedido."},
        {"type": "image_url", "image_url": {"url": data_url}},
    ]}
    reading, _ = client.chat_json(prompt, prompt.render(), PrintReading, model, [message])
    return reading


def aggregate(readings: list[dict]) -> dict:
    """Conta questões, acertos de primeira e tentativas erradas na ordem dos prints (D17).

    Prints sem número de questão: os errados se juntam ao próximo print certo (eu tiro print
    dos erros e depois do acerto da mesma questão).
    """
    questions: dict[str, dict] = {}
    pending_wrong = 0
    seq = 0
    for r in readings:
        if r["result"] == "unknown":
            continue
        if r["question_number"] is not None:
            q = questions.setdefault(f"n{r['question_number']}", {"wrong": 0, "correct": False})
            if r["result"] == "wrong":
                q["wrong"] += 1
            else:
                q["correct"] = True
            continue
        if r["result"] == "wrong":
            pending_wrong += 1
        else:
            seq += 1
            questions[f"s{seq}"] = {"wrong": pending_wrong, "correct": True}
            pending_wrong = 0
    if pending_wrong:
        seq += 1
        questions[f"s{seq}"] = {"wrong": pending_wrong, "correct": False}
    total = len(questions)
    first = sum(1 for q in questions.values() if q["correct"] and q["wrong"] == 0)
    wrong = sum(q["wrong"] for q in questions.values())
    return {"total_questions": total, "first_try_correct": first, "wrong_attempts": wrong,
            "score": round(first / total * 10, 1) if total else None}


# --- API ---------------------------------------------------------------------

router = APIRouter(prefix="/api/prints", tags=["notas pelos prints"])


def _client(request: Request, session: Session) -> LLMClient:
    return LLMClient(session, transport=getattr(request.app.state, "llm_transport", None))


def _vision_model(session: Session, model: str | None) -> str | None:
    return model or settings_store.get(session, "vision_model") or None


@router.get("/status")
def status(session: Session = Depends(get_session)):
    root = materials_dir()
    return {"materials_available": root.is_dir() and any(root.iterdir()) if root.is_dir() else False,
            "vision_model": settings_store.get(session, "vision_model"),
            "default_model": settings_store.get(session, "default_model")}


@router.get("/folder")
def list_folder(path: str = Query("", max_length=500), kind: Literal["prints", "transcripts"] = "prints"):
    """Pastas e arquivos de um nível da pasta de materiais: imagens e PDFs, ou transcrições (v1.6)."""
    target = safe_path(path)
    if not target.is_dir():
        raise HTTPException(404, "Pasta não encontrada (a pasta de materiais está montada no Docker?).")
    root = materials_dir().resolve()
    entries = []
    for f in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if f.name.startswith("."):
            continue
        if f.is_dir():
            entries.append({"name": f.name, "path": str(f.relative_to(root)), "type": "dir"})
        elif kind == "transcripts" and f.suffix.lower() in TRANSCRIPT_EXT:
            entries.append({"name": f.name, "path": str(f.relative_to(root)), "type": "transcript",
                            "size": f.stat().st_size})
        elif kind == "prints" and f.suffix.lower() in IMAGE_EXT | PDF_EXT:
            entries.append({"name": f.name, "path": str(f.relative_to(root)),
                            "type": "pdf" if f.suffix.lower() in PDF_EXT else "image", "size": f.stat().st_size})
    return {"path": "" if target == root else str(target.relative_to(root)), "entries": entries}


def _item_page(session: Session, topic_id: int | None, deadline_id: int | None) -> str:
    """Página ligada a um tema ou ao próprio item (laboratório, atividade, simulado). Nada além disso (D17)."""
    if deadline_id is not None:
        d = session.get(models.Deadline, deadline_id)
        if d is None:
            raise HTTPException(404, "item não encontrado")
        if not d.notion_page_id:
            raise HTTPException(409, "Este item ainda não tem página do Notion ligada.")
        return d.notion_page_id
    if topic_id is None:
        raise HTTPException(422, "Escolha o tema ou ligue a página do item.")
    return _topic_page(session, topic_id)


def _topic_page(session: Session, topic_id: int) -> str:
    topic = session.get(models.Topic, topic_id)
    if topic is None:
        raise HTTPException(404, "tema não encontrado")
    if not topic.notion_page_id:
        raise HTTPException(409, "Este tema ainda não tem página do Notion ligada (Gerenciar → Disciplinas e temas).")
    return topic.notion_page_id


@router.get("/notion-sections")
def notion_sections(request: Request, topic_id: int | None = None, deadline_id: int | None = None,
                    session: Session = Depends(get_session)):
    """Títulos da página (do tema ou do próprio item) e quantas imagens há em cada um."""
    page = _item_page(session, topic_id, deadline_id)
    try:
        images = notion.NotionClient(notion.transport_of(request), notion.sleep_of(request)).page_images(page)
    except notion.NotionError as exc:
        raise HTTPException(502, str(exc)) from exc
    counts: dict[str, int] = {}
    for img in images:
        counts[img["section"]] = counts.get(img["section"], 0) + 1
    return [{"section": k, "images": v} for k, v in counts.items()]


class AnalyzeIn(BaseModel):
    source: Literal["notion", "folder"]
    topic_id: int | None = None
    deadline_id: int | None = None
    section: str | None = Field(default=None, max_length=200)
    paths: list[str] = Field(default_factory=list, max_length=50)
    model: str | None = None


def collect_sources(request: Request, session: Session, source: str, topic_id: int | None, deadline_id: int | None,
                    section: str | None, paths: list[str]) -> list[dict]:
    """Imagens escolhidas: página do Notion (tema ou item, toda ou uma seção) ou arquivos da pasta."""
    if source == "notion":
        page = _item_page(session, topic_id, deadline_id)
        try:
            found = notion.NotionClient(notion.transport_of(request), notion.sleep_of(request)).page_images(page)
        except notion.NotionError as exc:
            raise HTTPException(502, str(exc)) from exc
        if section:
            found = [f for f in found if f["section"] == section]
        sources = [{"label": f"{f['section']} · imagem {i}", "url": f["url"]} for i, f in enumerate(found, start=1)]
    else:
        if not paths:
            raise HTTPException(422, "Escolha os arquivos ou a pasta com os prints.")
        sources = folder_images(paths)
    if not sources:
        raise HTTPException(409, "Não encontrei imagens nessa escolha.")
    if len(sources) > MAX_IMAGES:
        raise HTTPException(413, f"São {len(sources)} imagens; escolha no máximo {MAX_IMAGES} por vez "
                                 "(uma seção do Notion ou uma pasta menor).")
    return sources


@router.post("/analyze")
def analyze(data: AnalyzeIn, request: Request, session: Session = Depends(get_session)):
    """Lê os prints e devolve uma PROPOSTA de acertos, erros e nota. Não grava nada."""
    sources = collect_sources(request, session, data.source, data.topic_id, data.deadline_id, data.section,
                              data.paths)

    client = _client(request, session)
    model = _vision_model(session, data.model)
    image_transport = getattr(request.app.state, "image_transport", None)
    readings = []
    for src in sources:
        item = {"label": src["label"], "question_number": None, "result": "unknown", "note": ""}
        try:
            raw = src["raw"] if "raw" in src else download(src["url"], image_transport)
            reading = read_image(client, to_data_url(raw), model)
            item.update(reading.model_dump())
        except LLMError as exc:
            if exc.status in ("no_model", "error") and not readings:
                # O primeiro já falhou por falta de modelo ou servidor fora: não adianta seguir
                raise HTTPException(422 if exc.status == "no_model" else 502,
                                    {"message": str(exc), "status": exc.status}) from exc
            item["note"] = f"o modelo não conseguiu ler: {exc}"[:200]
        except (ValueError, httpx.HTTPError) as exc:
            item["note"] = f"imagem não lida: {exc}"[:200]
        readings.append(item)
    return {"images": len(readings), "readings": readings, **aggregate(readings),
            "unknown": sum(1 for r in readings if r["result"] == "unknown")}


class VisionCheckIn(BaseModel):
    model: str | None = None


def _number_image(n: int) -> str:
    img = Image.new("RGB", (256, 256), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=180)
    except TypeError:  # Pillow antigo
        font = ImageFont.load_default()
    draw.text((128, 128), str(n), fill="black", font=font, anchor="mm")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return to_data_url(buf.getvalue())


@router.post("/check-vision")
def check_vision(data: VisionCheckIn, request: Request, session: Session = Depends(get_session)):
    """Manda uma imagem com o número 7 e confere se o modelo lê (antes de confiar nas notas)."""
    client = _client(request, session)
    model = _vision_model(session, data.model)
    prompt = prompts.load("vision_check")
    message = {"role": "user", "content": [
        {"type": "text", "text": "Qual é o número? Responda só com o JSON pedido."},
        {"type": "image_url", "image_url": {"url": _number_image(7)}},
    ]}
    try:
        reading, used = client.chat_json(prompt, prompt.render(), NumberReading, model, [message])
    except LLMError as exc:
        return {"ok": False, "model": model, "message": str(exc)}
    ok = reading.number == 7
    return {"ok": ok, "model": used,
            "message": "O modelo leu a imagem certo." if ok
            else f"O modelo respondeu {reading.number} para uma imagem com 7: ele não lê imagens bem."}
