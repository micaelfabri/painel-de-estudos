"""Google Agenda (SPEC D7, F5).

Decisões (10/11/2026): o painel cria a própria agenda "Painel de Estudos" (uma camada) e só escreve nela;
lê os eventos da agenda principal para a faixa de 14 dias; nunca apaga nada; só edita eventos com a
propriedade estendida privada painel=1.

Escopos mínimos:
- calendar.app.created: criar a agenda do painel e mexer só nos eventos dela;
- calendar.events.readonly: ler eventos (agenda principal), sem poder alterar.

Credenciais: secrets/google_client.json (baixado do Google, tipo "App para computador") e
secrets/google_token.json (criado no primeiro login). Os dois ficam fora do git.
"""

import base64
import hashlib
import json
import logging
import os
import secrets as pysecrets
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models, settings_store
from ..db import get_session

log = logging.getLogger("painel.google")

SCOPES = ["https://www.googleapis.com/auth/calendar.app.created",
          "https://www.googleapis.com/auth/calendar.events.readonly"]
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/calendar/v3"
TZ = "America/Sao_Paulo"
CALENDAR_NAME = "Painel de Estudos"
EXAM_HOURS = 1  # duração padrão da prova (1 h, 10 questões); ajuste à sua faculdade

_pending: dict[str, str] = {}  # state -> code_verifier do login em andamento


class GoogleError(Exception):
    pass


def secrets_dir() -> Path:
    return Path(os.environ.get("PAINEL_SECRETS_DIR", Path(__file__).resolve().parents[3] / "secrets"))


def client_file() -> Path:
    return secrets_dir() / "google_client.json"


def token_file() -> Path:
    return secrets_dir() / "google_token.json"


def _client_info() -> dict:
    try:
        data = json.loads(client_file().read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GoogleError("Falta o secrets/google_client.json (veja o guia, seção 7).") from exc
    except ValueError as exc:
        raise GoogleError("O secrets/google_client.json não é um JSON válido.") from exc
    info = data.get("installed") or data.get("web")
    if not info or "client_id" not in info:
        raise GoogleError("O google_client.json não é de um cliente OAuth \"App para computador\".")
    return info


def redirect_uri(request: Request) -> str:
    # Cliente "App para computador" aceita retorno em localhost (loopback)
    return f"http://localhost:{request.url.port or 8000}/api/google/callback"


def start_login(request: Request) -> str:
    info = _client_info()
    verifier = pysecrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = pysecrets.token_urlsafe(24)
    _pending.clear()  # um login por vez
    _pending[state] = verifier
    params = {"client_id": info["client_id"], "redirect_uri": redirect_uri(request), "response_type": "code",
              "scope": " ".join(SCOPES), "access_type": "offline", "prompt": "consent", "state": state,
              "code_challenge": challenge, "code_challenge_method": "S256"}
    return f"{AUTH_URL}?{urlencode(params)}"


def finish_login(request: Request, code: str, state: str, transport: httpx.BaseTransport | None) -> None:
    verifier = _pending.pop(state, None)
    if verifier is None:
        raise GoogleError("Login expirado ou de outra aba. Clique em \"Conectar Google\" de novo.")
    info = _client_info()
    with httpx.Client(transport=transport, timeout=20) as http:
        res = http.post(TOKEN_URL, data={
            "code": code, "client_id": info["client_id"], "client_secret": info.get("client_secret", ""),
            "redirect_uri": redirect_uri(request), "grant_type": "authorization_code", "code_verifier": verifier})
    if res.status_code != 200:
        raise GoogleError(f"O Google recusou o login ({res.status_code}).")
    _save_token(res.json())


def _save_token(data: dict, keep_refresh: str | None = None) -> None:
    token = {"access_token": data["access_token"], "expires_at": time.time() + int(data.get("expires_in", 3600)) - 60,
             "refresh_token": data.get("refresh_token") or keep_refresh, "scope": data.get("scope", "")}
    path = token_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(token), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


class CalendarClient:
    def __init__(self, transport: httpx.BaseTransport | None = None):
        self.transport = transport
        self._token = self._load_token()
        self.http = httpx.Client(base_url=API, transport=transport, timeout=20,
                                 headers={"Authorization": f"Bearer {self._token['access_token']}"})

    def _load_token(self) -> dict:
        try:
            tok = json.loads(token_file().read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise GoogleError("Google ainda não conectado. Clique em \"Conectar Google\" em Configurações.") from exc
        if tok.get("expires_at", 0) > time.time():
            return tok
        if not tok.get("refresh_token"):
            raise GoogleError("Login do Google expirou. Clique em \"Conectar Google\" de novo.")
        info = _client_info()
        with httpx.Client(transport=self.transport, timeout=20) as http:
            res = http.post(TOKEN_URL, data={"client_id": info["client_id"], "client_secret": info.get("client_secret", ""),
                                             "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"})
        if res.status_code != 200:
            raise GoogleError("Login do Google expirou ou foi revogado. Clique em \"Conectar Google\" de novo.")
        _save_token(res.json(), keep_refresh=tok["refresh_token"])
        return json.loads(token_file().read_text(encoding="utf-8"))

    def _req(self, method: str, path: str, **kw) -> dict:
        if method == "DELETE":  # regra do projeto: nunca apagar
            raise GoogleError("Apagar eventos não é permitido.")
        try:
            res = self.http.request(method, path, **kw)
        except httpx.HTTPError as exc:
            raise GoogleError(f"Não foi possível falar com o Google: {exc.__class__.__name__}") from exc
        if res.status_code == 404:
            raise LookupError(path)
        if res.status_code >= 400:
            try:
                msg = res.json().get("error", {}).get("message", "")
            except ValueError:
                msg = ""
            raise GoogleError(f"Erro do Google Agenda ({res.status_code}): {msg[:200]}")
        return res.json()

    # --- agenda do painel ----------------------------------------------------

    def ensure_calendar(self, session: Session) -> str:
        cal_id = settings_store.get(session, "calendar_id")
        if cal_id:
            try:
                self._req("GET", f"/calendars/{cal_id}")
                return cal_id
            except LookupError:
                log.info("Agenda do painel não existe mais; criando outra")
        cal = self._req("POST", "/calendars", json={"summary": CALENDAR_NAME, "timeZone": TZ,
                                                     "description": "Provas criadas pelo Painel de Estudos."})
        settings_store.put(session, "calendar_id", cal["id"])
        session.commit()
        return cal["id"]

    def upsert_exam(self, cal_id: str, exam: models.Exam) -> tuple[str, str]:
        start = exam.scheduled_at
        body = {
            "summary": f"Prova · {exam.subject.name}",
            "location": exam.location or "",
            "description": f"{exam.kind} · criado pelo Painel de Estudos",
            "start": {"dateTime": start.isoformat(timespec="seconds"), "timeZone": TZ},
            "end": {"dateTime": (start + timedelta(hours=EXAM_HOURS)).isoformat(timespec="seconds"), "timeZone": TZ},
            "extendedProperties": {"private": {"painel": "1", "exam_id": str(exam.id)}},
        }
        if exam.gcal_event_id:
            try:
                current = self._req("GET", f"/calendars/{cal_id}/events/{exam.gcal_event_id}")
                if (current.get("extendedProperties", {}).get("private", {}).get("painel") == "1"
                        and current.get("status") != "cancelled"):
                    self._req("PATCH", f"/calendars/{cal_id}/events/{exam.gcal_event_id}", json=body)
                    return exam.gcal_event_id, "updated"
            except LookupError:
                pass  # evento sumiu (ou é de outra agenda): cria de novo
        created = self._req("POST", f"/calendars/{cal_id}/events", json=body)
        return created["id"], "created"

    def events(self, start: date, end: date, calendar: str = "primary") -> list[dict]:
        data = self._req("GET", f"/calendars/{calendar}/events", params={
            "timeMin": f"{start.isoformat()}T00:00:00-03:00", "timeMax": f"{end.isoformat()}T00:00:00-03:00",
            "singleEvents": "true", "orderBy": "startTime", "maxResults": 250})
        out = []
        for e in data.get("items", []):
            if e.get("extendedProperties", {}).get("private", {}).get("painel") == "1":
                continue  # as provas do painel já aparecem pela própria base
            s = e.get("start", {})
            out.append({"title": e.get("summary") or "(sem título)",
                        "date": (s.get("dateTime") or s.get("date") or "")[:10],
                        "time": s["dateTime"][11:16] if s.get("dateTime") else None})
        return out


def sync_exams(session: Session, transport: httpx.BaseTransport | None = None) -> dict:
    client = CalendarClient(transport)
    cal_id = client.ensure_calendar(session)
    exams = session.scalars(
        select(models.Exam).where(models.Exam.scheduled_at.is_not(None)).options(selectinload(models.Exam.subject))
    ).all()
    counts = {"created": 0, "updated": 0}
    for exam in exams:
        event_id, what = client.upsert_exam(cal_id, exam)
        exam.gcal_event_id = event_id
        counts[what] += 1
    session.commit()
    return counts


# --- API ---------------------------------------------------------------------

router = APIRouter(prefix="/api/google", tags=["google"])


def transport_of(request: Request) -> httpx.BaseTransport | None:
    return getattr(request.app.state, "google_transport", None)


@router.get("/status")
def status(session: Session = Depends(get_session)):
    has_client = client_file().exists()
    connected = token_file().exists()
    return {"client_file": has_client, "connected": connected,
            "calendar_id": settings_store.get(session, "calendar_id"), "calendar_name": CALENDAR_NAME}


@router.get("/login")
def login(request: Request):
    try:
        return RedirectResponse(start_login(request), status_code=302)
    except GoogleError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/callback")
def callback(request: Request, code: str | None = None, state: str = "", error: str | None = None):
    if error or not code:
        return RedirectResponse("/gerenciar/configuracoes?google=cancelado", status_code=302)
    try:
        finish_login(request, code, state, transport_of(request))
    except GoogleError as exc:
        log.warning("Google: login falhou: %s", exc)
        return RedirectResponse("/gerenciar/configuracoes?google=erro", status_code=302)
    return RedirectResponse("/gerenciar/configuracoes?google=ok", status_code=302)


@router.post("/sync-exams")
def sync(request: Request, session: Session = Depends(get_session)):
    try:
        return sync_exams(session, transport_of(request))
    except GoogleError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/events")
def events(request: Request, start: date | None = Query(None), days: int = Query(14, ge=1, le=60)):
    """Eventos da agenda principal (só leitura) para a faixa de dias do painel."""
    start = start or date.today()
    if not token_file().exists():
        return {"connected": False, "events": []}
    try:
        items = CalendarClient(transport_of(request)).events(start, start + timedelta(days=days))
    except GoogleError as exc:
        return {"connected": True, "events": [], "error": str(exc)}
    return {"connected": True, "events": items}
