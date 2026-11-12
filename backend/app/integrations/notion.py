"""Notion (SPEC D6, F5): ler o texto do tema e gravar o resultado no fim da página.

Regras: token só no .env (NOTION_TOKEN); só enxerga páginas compartilhadas com a conexão;
nunca apaga páginas nem blocos — só acrescenta no fim.
"""

import logging
import os
import time
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..db import get_session
from ..learning import LABELS

log = logging.getLogger("painel.notion")

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
MAX_RETRIES = 4  # novas tentativas depois de um 429
MIN_INTERVAL = 0.34  # segundos entre requisições (~3 por segundo, limite do Notion)
MAX_PAGES = 500
MAX_DEPTH = 3  # filhos de toggles/listas dentro do texto do tema
TEXT_TYPES = {
    "paragraph": "", "heading_1": "# ", "heading_2": "## ", "heading_3": "### ", "bulleted_list_item": "- ",
    "numbered_list_item": "1. ", "to_do": "- [ ] ", "toggle": "", "quote": "> ", "callout": "", "code": "",
}


class NotionError(Exception):
    pass


def token() -> str | None:
    return os.environ.get("NOTION_TOKEN") or None


class NotionClient:
    def __init__(self, transport: httpx.BaseTransport | None = None, sleep=time.sleep):
        self._sleep = sleep
        self._last = 0.0
        tok = token()
        if not tok:
            raise NotionError("NOTION_TOKEN não está no .env")
        self._http = httpx.Client(
            base_url=API, transport=transport, timeout=httpx.Timeout(20.0),
            headers={"Authorization": f"Bearer {tok}", "Notion-Version": VERSION},
        )

    def _req(self, method: str, path: str, **kw) -> dict:
        # O Notion aceita ~3 requisições/s: espaça as chamadas e respeita o Retry-After de um 429
        for attempt in range(MAX_RETRIES + 1):
            wait = MIN_INTERVAL - (time.monotonic() - self._last)
            if wait > 0:
                self._sleep(wait)
            self._last = time.monotonic()
            try:
                res = self._http.request(method, path, **kw)
            except httpx.HTTPError as exc:
                raise NotionError(f"Não foi possível falar com o Notion: {exc.__class__.__name__}") from exc
            if res.status_code == 429 and attempt < MAX_RETRIES:
                try:
                    delay = float(res.headers.get("Retry-After", "1"))
                except ValueError:
                    delay = 1.0
                self._sleep(min(max(delay, 0.5), 30.0))
                continue
            break
        if res.status_code == 401:
            raise NotionError("O Notion recusou o token (401). Confira o NOTION_TOKEN no .env.")
        if res.status_code == 404:
            raise NotionError("Página não encontrada ou não compartilhada com a conexão \"Painel de Estudos\".")
        if res.status_code == 429:
            raise NotionError("O Notion está limitando as requisições (429). Tente de novo em 1 minuto.")
        if res.status_code >= 400:
            msg = res.json().get("message", "") if "json" in res.headers.get("content-type", "") else ""
            raise NotionError(f"Erro do Notion ({res.status_code}): {msg[:200]}")
        return res.json()

    def search_pages(self, query: str = "") -> list[dict]:
        out, cursor = [], None
        while len(out) < MAX_PAGES:
            body = {"filter": {"value": "page", "property": "object"}, "page_size": 100,
                    "sort": {"direction": "descending", "timestamp": "last_edited_time"}}
            if query:
                body["query"] = query
            if cursor:
                body["start_cursor"] = cursor
            data = self._req("POST", "/search", json=body)
            out += [{"id": p["id"], "title": page_title(p), "url": p.get("url"),
                     "last_edited": p.get("last_edited_time")} for p in data.get("results", [])]
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        return out[:MAX_PAGES]

    def children(self, block_id: str) -> list[dict]:
        out, cursor = [], None
        while True:
            params = {"page_size": 100, **({"start_cursor": cursor} if cursor else {})}
            data = self._req("GET", f"/blocks/{block_id}/children", params=params)
            out += data.get("results", [])
            if not data.get("has_more"):
                return out
            cursor = data.get("next_cursor")

    def page_text(self, page_id: str) -> str:
        lines: list[str] = []
        self._collect(page_id, lines, 0)
        return "\n".join(lines).strip()

    def _collect(self, block_id: str, lines: list[str], depth: int) -> None:
        for b in self.children(block_id):
            kind = b.get("type")
            if kind in TEXT_TYPES:
                text = "".join(t.get("plain_text", "") for t in b[kind].get("rich_text", []))
                if text.strip():
                    lines.append(("  " * depth) + TEXT_TYPES[kind] + text)
            # Imagens, arquivos, embeds e bancos de dados ficam de fora: só texto vai ao modelo
            if b.get("has_children") and depth < MAX_DEPTH and kind not in ("child_page", "child_database"):
                self._collect(b["id"], lines, depth + 1)

    def append(self, page_id: str, blocks: list[dict]) -> None:
        # PATCH em children = acrescentar no fim; nunca usa DELETE
        self._req("PATCH", f"/blocks/{page_id}/children", json={"children": blocks})


def sections(text: str) -> list[dict]:
    """Divide o texto pelos títulos do nível de cima (# e ##) para escolher um módulo só."""
    out: list[dict] = []
    for line in text.split("\n"):
        if line.startswith(("# ", "## ")) or not out:
            title = line.lstrip("# ").strip() if line.startswith(("# ", "## ")) else "Início"
            out.append({"title": title, "lines": []})
        out[-1]["lines"].append(line)
    result = []
    for sec in out:
        body = "\n".join(sec["lines"]).strip()
        if body:
            result.append({"title": sec["title"][:120], "chars": len(body), "text": body})
    return result


def page_title(page: dict) -> str:
    for prop in (page.get("properties") or {}).values():
        if prop.get("type") == "title":
            return "".join(t.get("plain_text", "") for t in prop.get("title", [])) or "(sem título)"
    return "(sem título)"


def _text(content: str) -> list[dict]:
    return [{"type": "text", "text": {"content": content[:1900]}}]


def result_blocks(session: Session, qs: models.QuestionSet) -> list[dict]:
    """Bloco gravado no fim da página: título com data e tipo, nota e as questões erradas."""
    when = (qs.completed_at or datetime.now()).strftime("%d/%m/%Y")
    valid = [q for q in qs.questions if not q.flagged_bad]
    right = sum(1 for q in valid if q.answer and q.answer.is_correct)
    blocks = [
        {"object": "block", "type": "heading_3",
         "heading_3": {"rich_text": _text(f"Painel de Estudos · {LABELS.get(qs.attempt_type, qs.attempt_type)} · {when}")}},
        {"object": "block", "type": "paragraph",
         "paragraph": {"rich_text": _text(f"Nota: {round((qs.score or 0) * 100)}% ({right} de {len(valid)}) · modelo {qs.model}")}},
    ]
    wrong = [q for q in valid if q.answer and not q.answer.is_correct]
    if wrong:
        blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": _text("Para rever:")}})
        for q in wrong:
            minute = next((m.video_minute for m in session.scalars(
                select(models.Mistake).where(models.Mistake.question_id == q.id)) if m.video_minute), None)
            extra = f" (vídeo {minute})" if minute else ""
            blocks.append({"object": "block", "type": "bulleted_list_item",
                           "bulleted_list_item": {"rich_text": _text(
                               f"{q.statement} → certa: {q.options[q.correct_index]}{extra}")}})
    return blocks


def sync_set(session: Session, qs: models.QuestionSet, transport: httpx.BaseTransport | None = None) -> str:
    """Grava o resultado de um conjunto concluído. Devolve ok | skipped | erro (texto curto)."""
    topic = session.get(models.Topic, qs.topic_id)
    if qs.completed_at is None or qs.notion_synced_at is not None:
        return "skipped"
    if not topic.notion_page_id or not token():
        return "skipped"
    try:
        NotionClient(transport).append(topic.notion_page_id, result_blocks(session, qs))
    except NotionError as exc:
        log.warning("Notion: resultado do conjunto %s não gravado: %s", qs.id, exc)
        return str(exc)
    qs.notion_synced_at = datetime.now()
    return "ok"


# --- API ---------------------------------------------------------------------

router = APIRouter(prefix="/api/notion", tags=["notion"])


def transport_of(request: Request) -> httpx.BaseTransport | None:
    # Testes injetam um transporte falso em app.state.notion_transport
    return getattr(request.app.state, "notion_transport", None)


def sleep_of(request: Request):
    # Testes trocam a pausa entre requisições por uma função que só registra
    return getattr(request.app.state, "notion_sleep", time.sleep)


def _client(request: Request) -> NotionClient:
    try:
        return NotionClient(transport_of(request), sleep_of(request))
    except NotionError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/status")
def status(request: Request, session: Session = Depends(get_session)):
    configured = token() is not None
    pending = session.scalars(
        select(models.QuestionSet).join(models.Topic)
        .where(models.QuestionSet.completed_at.is_not(None), models.QuestionSet.notion_synced_at.is_(None),
               models.Topic.notion_page_id.is_not(None))
    ).all()
    out = {"configured": configured, "reachable": False, "pages": 0, "pending_results": len(pending), "error": None}
    if configured:
        try:
            out["pages"] = len(NotionClient(transport_of(request), sleep_of(request)).search_pages())
            out["reachable"] = True
        except NotionError as exc:
            out["error"] = str(exc)
    return out


@router.get("/pages")
def pages(request: Request, q: str = Query("", max_length=100)):
    try:
        return _client(request).search_pages(q)
    except NotionError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.get("/topics/{topic_id}/text")
def topic_text(topic_id: int, request: Request, session: Session = Depends(get_session)):
    """Texto da página do Notion ligada ao tema (só texto; imagens ficam de fora)."""
    topic = session.get(models.Topic, topic_id)
    if topic is None:
        raise HTTPException(404, "tema não encontrado")
    if not topic.notion_page_id:
        raise HTTPException(409, "Este tema ainda não tem página do Notion ligada (Gerenciar → Disciplinas e temas).")
    try:
        text = _client(request).page_text(topic.notion_page_id)
    except NotionError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"topic_id": topic_id, "chars": len(text), "text": text, "sections": sections(text)}


@router.post("/sync")
def sync_pending(request: Request, session: Session = Depends(get_session)):
    """Grava no Notion os resultados que ainda não foram (ex.: Notion fora do ar na hora)."""
    sets = session.scalars(
        select(models.QuestionSet).where(models.QuestionSet.completed_at.is_not(None),
                                         models.QuestionSet.notion_synced_at.is_(None))
    ).all()
    results = [sync_set(session, qs, transport_of(request)) for qs in sets]
    session.commit()
    return {"ok": results.count("ok"), "skipped": results.count("skipped"),
            "errors": [r for r in results if r not in ("ok", "skipped")][:5]}
