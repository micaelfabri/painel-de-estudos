"""Configurações do app guardadas na tabela `setting`.

Só chaves conhecidas são aceitas; cada uma tem tipo e valor padrão. Valores
`None` são pendências que o dono preenche no modo Gerenciar.
"""

from typing import Any

from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from .models import Setting

# chave -> (tipo, padrão, descrição)
KNOWN: dict[str, tuple[Any, Any, str]] = {
    "llm_base_url": (str, "http://host.docker.internal:11434/v1", "Endereço da API compatível com OpenAI (Ollama ou LM Studio)"),
    "default_model": (str | None, None, "Modelo padrão do agente (escolhido na F0)"),
    "llm_timeout_seconds": (int, 900, "Tempo máximo de espera por resposta do modelo, em segundos (30 a 3600)"),
    "weekly_hours_goal": (float | None, None, "Meta de horas de estudo por semana"),
    "timer_goal_minutes": (int, 90, "Meta do cronômetro por tema, em minutos"),
    "timer_alarm_minutes": (int, 120, "Alarme do cronômetro, em minutos"),
    "questions_per_set": (int, 10, "Questões por conjunto (estilo da prova)"),
    "options_per_question": (int | None, None, "Alternativas por questão (a confirmar numa prova real)"),
    "learned_threshold": (float, 0.7, "Nota mínima no reteste de 7 dias para 'aprendido'"),
    "calendar_id": (str | None, None, "ID da agenda do Google usada pelo painel"),
    "notion_page_ids": (list[str], [], "Páginas do Notion compartilhadas com a integração"),
    "course_weekly_goal_hours": (float | None, 5.0, "Meta de horas por semana nos cursos fora da faculdade (D41)"),
    "courses_in_day_plan": (bool, False, "Os cursos entram no \"Montar o dia\" (retestes e próxima aula) (D40)"),
    "exam_minutes": (int, 60, "Tempo do simulado da prova, em minutos (D16)"),
    "agent_reads_metrics": (bool, True, "O agente pode ler um resumo dos meus números de estudo (horas, notas, temas)"),
    "vision_model": (str | None, None, "Modelo que lê imagens, para as notas pelos prints (vazio = modelo padrão)"),
    "github_url": (str | None, None, "Link do GitHub no rodapé"),
    "linkedin_url": (str | None, None, "Link do LinkedIn no rodapé"),
    "site_url": (str | None, None, "Link do site pessoal no rodapé (vazio = 'em breve')"),
}


def _adapter(key: str) -> TypeAdapter:
    return TypeAdapter(KNOWN[key][0])


def get_all(session: Session) -> dict[str, Any]:
    stored = {s.key: s.value for s in session.query(Setting).all()}
    return {key: stored.get(key, default) for key, (_t, default, _d) in KNOWN.items()}


def get(session: Session, key: str) -> Any:
    row = session.get(Setting, key)
    return row.value if row else KNOWN[key][1]


def put(session: Session, key: str, value: Any) -> Any:
    if key not in KNOWN:
        raise KeyError(key)
    value = _adapter(key).validate_python(value)
    if key == "llm_base_url":
        _check_llm_url(value)
    if key in ("github_url", "linkedin_url", "site_url") and value:
        _check_https(value)
    if key == "exam_minutes" and not 5 <= value <= 300:
        raise ValueError("exam_minutes precisa ficar entre 5 e 300")
    if key == "llm_timeout_seconds" and not 30 <= value <= 3600:
        raise ValueError("llm_timeout_seconds precisa ficar entre 30 e 3600")
    row = session.get(Setting, key)
    if row:
        row.value = value
    else:
        session.add(Setting(key=key, value=value))
    session.commit()
    return value


def _check_llm_url(value: str) -> None:
    """Aceita só http(s) com host (auditoria: evita esquemas como file:// ou URLs sem host)."""
    from urllib.parse import urlsplit

    parts = urlsplit(value.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("llm_base_url precisa ser http:// ou https:// com host")


def _check_https(value: str) -> None:
    """Links do rodapé: só https:// com host (vão para href)."""
    from urllib.parse import urlsplit

    parts = urlsplit(value.strip())
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError("o link precisa começar com https://")


def describe() -> list[dict[str, Any]]:
    return [{"key": k, "default": d, "description": desc} for k, (_t, d, desc) in KNOWN.items()]
