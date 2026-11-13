"""Aplicação FastAPI: API em /api e, quando existir, o frontend compilado em /."""

import os
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import cards, course, courses, learning, models, overview, schemas, settings_store, study
from .agent.router import router as agent_router
from .crud import crud_router
from .db import get_session
from .grading import PRESETS, GradeInput, GradeResult, GradingRule, evaluate
from .integrations import google_calendar, notion, prints

app = FastAPI(title="Painel de Estudos", version="0.1.0")

# --- Endurecimento (auditoria de segurança, docs/security-audit) --------------
# Host permitido: bloqueia DNS rebinding (um site externo apontando um domínio para 127.0.0.1).
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("PAINEL_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self' data:; connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'"
    ),
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response


UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def block_cross_site_writes(request: Request, call_next):
    # CSRF: um site aberto no navegador pode mandar POST simples (sem corpo) para 127.0.0.1.
    # Escritas só valem vindas da própria página do painel (ou de ferramentas sem navegador).
    if request.method in UNSAFE_METHODS:
        site = request.headers.get("sec-fetch-site")
        origin = request.headers.get("origin")
        foreign_origin = origin is not None and urlsplit(origin).hostname not in ALLOWED_HOSTS
        if site not in (None, "same-origin", "none") or foreign_origin:
            return JSONResponse({"detail": "Requisição de outro site bloqueada."}, status_code=403)
    return await call_next(request)


@app.get("/api/health", tags=["sistema"])
def health():
    return {"status": "ok"}


# --- Cadastros (modo Gerenciar) ----------------------------------------------

app.include_router(
    crud_router(prefix="/api/degrees", model=models.Degree, schema_in=schemas.DegreeIn,
                schema_out=schemas.DegreeOut, tag="graduações")
)
app.include_router(
    crud_router(prefix="/api/degree-components", model=models.DegreeComponent, schema_in=schemas.DegreeComponentIn,
                schema_out=schemas.DegreeComponentOut, filters=("degree_id",), tag="componentes")
)
app.include_router(
    crud_router(prefix="/api/semesters", model=models.Semester, schema_in=schemas.SemesterIn,
                schema_out=schemas.SemesterOut, filters=("degree_id",), order_by=("code",), tag="semestres")
)
app.include_router(
    crud_router(prefix="/api/subjects", model=models.Subject, schema_in=schemas.SubjectIn,
                schema_out=schemas.SubjectOut, filters=("degree_id", "semester_id"), order_by=("name",),
                tag="disciplinas")
)
app.include_router(
    crud_router(prefix="/api/topics", model=models.Topic, schema_in=schemas.TopicIn, schema_out=schemas.TopicOut,
                filters=("subject_id",), order_by=("subject_id", "position"), tag="temas")
)
app.include_router(
    crud_router(prefix="/api/exams", model=models.Exam, schema_in=schemas.ExamIn, schema_out=schemas.ExamOut,
                filters=("subject_id",), tag="provas")
)
app.include_router(
    crud_router(prefix="/api/deadlines", model=models.Deadline, schema_in=schemas.DeadlineIn,
                schema_out=schemas.DeadlineOut, filters=("subject_id",), order_by=("due_date",), tag="prazos")
)
app.include_router(
    crud_router(prefix="/api/acc-activities", model=models.AccActivity, schema_in=schemas.AccActivityIn,
                schema_out=schemas.AccActivityOut, filters=("degree_id",), order_by=("activity_date",), tag="ACC")
)
app.include_router(
    crud_router(prefix="/api/study-sessions", model=models.StudySession, schema_in=schemas.StudySessionIn,
                schema_out=schemas.StudySessionOut, filters=("subject_id", "topic_id"), order_by=("started_at",),
                tag="sessões de estudo")
)
app.include_router(overview.router)
app.include_router(agent_router)
app.include_router(learning.router)
app.include_router(study.router)
app.include_router(cards.router)
app.include_router(prints.router)
app.include_router(course.router)
app.include_router(courses.router)
app.include_router(notion.router)
app.include_router(google_calendar.router)
app.include_router(
    crud_router(prefix="/api/mistakes", model=models.Mistake, schema_in=schemas.MistakeIn,
                schema_out=schemas.MistakeOut, filters=("topic_id",), tag="erros")
)
app.include_router(
    crud_router(prefix="/api/acc-rules", model=models.AccRule, schema_in=schemas.AccRuleIn,
                schema_out=schemas.AccRuleOut, filters=("degree_id",), tag="ACC")
)


# --- Progresso do portal (um registro por disciplina) -------------------------


@app.get("/api/subjects/{subject_id}/portal-progress", response_model=schemas.PortalProgressOut | None,
         tags=["progresso do portal"])
def get_portal_progress(subject_id: int, session: Session = Depends(get_session)):
    subject = session.get(models.Subject, subject_id)
    if subject is None:
        raise HTTPException(404, "disciplina não encontrada")
    return subject.portal_progress


@app.put("/api/subjects/{subject_id}/portal-progress", response_model=schemas.PortalProgressOut,
         tags=["progresso do portal"])
def put_portal_progress(subject_id: int, data: schemas.PortalProgressIn, session: Session = Depends(get_session)):
    subject = session.get(models.Subject, subject_id)
    if subject is None:
        raise HTTPException(404, "disciplina não encontrada")
    progress = subject.portal_progress or models.PortalProgress(subject_id=subject_id)
    for key, value in data.model_dump().items():
        setattr(progress, key, value)
    session.add(progress)
    session.commit()
    session.refresh(progress)
    return progress


# --- Regras de avaliação -----------------------------------------------------


@app.get("/api/grading-rules/presets", tags=["avaliação"])
def grading_presets():
    return PRESETS


@app.post("/api/subjects/{subject_id}/grade-check", response_model=GradeResult, tags=["avaliação"])
def grade_check(subject_id: int, data: GradeInput, session: Session = Depends(get_session)):
    """Simula a nota final com a regra da disciplina (não grava nada)."""
    subject = session.get(models.Subject, subject_id)
    if subject is None:
        raise HTTPException(404, "disciplina não encontrada")
    if not subject.grading_rule:
        raise HTTPException(422, "disciplina sem regra de avaliação")
    try:
        return evaluate(GradingRule.model_validate(subject.grading_rule), data)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


# --- Configurações -----------------------------------------------------------


@app.get("/api/settings", tags=["configurações"])
def list_settings(session: Session = Depends(get_session)):
    return {"values": settings_store.get_all(session), "schema": settings_store.describe()}


@app.put("/api/settings/{key}", tags=["configurações"])
def put_setting(key: str, data: schemas.SettingIn, session: Session = Depends(get_session)):
    try:
        value = settings_store.put(session, key, data.value)
    except KeyError as exc:
        raise HTTPException(404, f"configuração desconhecida: {key}") from exc
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_url=False)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"key": key, "value": value}


# --- Frontend compilado (quando existir) -------------------------------------

STATIC_DIR = Path(os.environ.get("PAINEL_STATIC_DIR", Path(__file__).resolve().parents[2] / "frontend" / "dist"))

if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        # Rotas do React caem sempre no index.html; arquivos reais são servidos direto
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file() and STATIC_DIR in candidate.resolve().parents:
            return FileResponse(candidate)
        if full_path.startswith("api/"):
            raise HTTPException(404)
        return FileResponse(STATIC_DIR / "index.html")
