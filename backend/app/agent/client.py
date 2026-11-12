"""Cliente único do modelo local (CLAUDE.md: toda chamada ao LLM passa por aqui).

- API compatível com OpenAI (Ollama /v1 ou LM Studio /v1), endereço nas configurações.
- Resposta sempre em JSON validado por um schema Pydantic; uma nova tentativa se vier inválido.
- Cada chamada fica registrada em `llm_call` (modelo, versão do prompt, tokens, tempo, status).
- Nenhum LLM em nuvem: o endereço padrão é o Ollama do próprio PC.
"""

import json
import re
import time
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from .. import models, settings_store
from .prompts import Prompt

T = TypeVar("T", bound=BaseModel)

# O modelo local pode levar dezenas de segundos; a interface oferece cancelar depois de 10 s
# Leitura: o modelo local pode levar minutos num texto longo (8 GB de GPU); vem de llm_timeout_seconds
def _timeout(read_seconds: float) -> httpx.Timeout:
    return httpx.Timeout(connect=5.0, read=read_seconds, write=30.0, pool=5.0)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I)


START_MESSAGE = "Siga as instruções acima e responda somente com o JSON pedido."

CUT_OFF_MESSAGE = (
    "A resposta do modelo foi cortada antes do fim. No LM Studio, aumente o Context Length do modelo "
    "(16384 ou mais) e desligue o modo de raciocínio (thinking), ou cole um trecho menor do tema."
)


def _server_error(res: httpx.Response) -> str:
    """Mensagem de erro que o servidor (Ollama/LM Studio) mandou, em texto curto."""
    try:
        body = res.json()
        err = body.get("error", body) if isinstance(body, dict) else body
        if isinstance(err, dict):
            err = err.get("message") or err
        return str(err)[:300]
    except ValueError:
        return res.text[:300]


def _is_context_error(detail: str) -> bool:
    low = detail.lower()
    return "context" in low and any(w in low for w in ("length", "exceed", "overflow", "greater", "tokens"))


class LLMError(Exception):
    """Falha ao falar com o modelo ou resposta inválida depois da nova tentativa."""

    def __init__(self, message: str, status: str = "error"):
        super().__init__(message)
        self.status = status


def _extract_json(content: str) -> object:
    text = _FENCE.sub("", content.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Alguns modelos escrevem algo antes/depois do JSON: pega o primeiro objeto completo
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])


class LLMClient:
    def __init__(self, session: Session, transport: httpx.BaseTransport | None = None):
        self.session = session
        self.base_url = str(settings_store.get(session, "llm_base_url")).rstrip("/")
        self._transport = transport

    def _http(self) -> httpx.Client:
        read = float(settings_store.get(self.session, "llm_timeout_seconds"))
        return httpx.Client(base_url=self.base_url, timeout=_timeout(read), transport=self._transport)

    def list_models(self) -> list[str]:
        with self._http() as http:
            res = http.get("/models")
            res.raise_for_status()
            body = res.json()
        # O Ollama sem modelos baixados responde {"data": null}; trata como lista vazia
        data = (body.get("data") if isinstance(body, dict) else None) or []
        return sorted(str(m["id"]) for m in data if isinstance(m, dict) and "id" in m)

    def resolve_model(self, model: str | None) -> str:
        chosen = model or settings_store.get(self.session, "default_model")
        if not chosen:
            raise LLMError("Nenhum modelo escolhido. Escolha um no painel do agente ou em Configurações.", "no_model")
        return chosen

    def chat_json(self, prompt: Prompt, rendered: str, schema: type[T], model: str | None = None,
                  history: list[dict] | None = None) -> tuple[T, str]:
        """Envia o prompt e devolve (objeto validado, modelo usado)."""
        model_name = self.resolve_model(model)
        messages = [{"role": "system", "content": rendered}, *(history or [])]
        if not any(m.get("role") == "user" for m in messages):
            # Alguns modelos (ex.: Qwen no LM Studio) recusam conversa sem mensagem do usuário:
            # "No user query found in messages". O pedido em si continua no prompt de sistema.
            messages.append({"role": "user", "content": START_MESSAGE})
        started = time.monotonic()
        tokens_in = tokens_out = 0
        attempts = 0
        last_error = ""
        # Formatos de saída, do mais rígido ao mais solto. O LM Studio recusa json_object (400) e aceita
        # json_schema; o Ollama aceita os dois. Num 400 passa para o próximo; a validação pelo schema
        # continua garantindo o formato em qualquer caso.
        formats: list[dict | None] = [
            {"type": "json_schema",
             "json_schema": {"name": schema.__name__, "strict": True, "schema": schema.model_json_schema()}},
            {"type": "json_object"},
            None,
        ]

        try:
            with self._http() as http:
                for attempts in (1, 2):
                    while True:
                        payload = {"model": model_name, "messages": messages, "temperature": 0.3, "stream": False}
                        if formats[0] is not None:
                            payload["response_format"] = formats[0]
                        res = http.post("/chat/completions", json=payload)
                        if res.status_code != 400:
                            break
                        detail = _server_error(res)
                        if _is_context_error(detail):
                            # Texto + resposta não cabem no contexto carregado no servidor
                            self._log(model_name, prompt, tokens_in, tokens_out, started, attempts, "error",
                                      f"contexto excedido: {detail}"[:500])
                            raise LLMError(CUT_OFF_MESSAGE, "cut_off")
                        if len(formats) == 1:
                            self._log(model_name, prompt, tokens_in, tokens_out, started, attempts, "error",
                                      f"400: {detail}"[:500])
                            raise LLMError(f"O servidor do modelo recusou o pedido: {detail[:200]}", "error")
                        formats.pop(0)
                    res.raise_for_status()
                    body = res.json()
                    usage = body.get("usage") or {}
                    tokens_in += usage.get("prompt_tokens") or 0
                    tokens_out += usage.get("completion_tokens") or 0
                    choice = body["choices"][0]
                    content = choice["message"].get("content") or ""
                    # Resposta cortada pelo limite de contexto (ou o "raciocínio" do modelo gastou tudo):
                    # repetir só pioraria, porque a nova tentativa manda ainda mais texto.
                    if choice.get("finish_reason") == "length" or (
                            not content.strip() and choice["message"].get("reasoning_content")):
                        self._log(model_name, prompt, tokens_in, tokens_out, started, attempts, "invalid_json",
                                  f"resposta cortada (finish_reason={choice.get('finish_reason')}, "
                                  f"tokens entrada={tokens_in}, saída={tokens_out})")
                        raise LLMError(CUT_OFF_MESSAGE, "cut_off")
                    try:
                        parsed = schema.model_validate(_extract_json(content))
                        self._log(model_name, prompt, tokens_in, tokens_out, started, attempts, "ok")
                        return parsed, model_name
                    except (json.JSONDecodeError, ValidationError) as exc:
                        last_error = str(exc)[:500]
                        # Nova tentativa: mostra ao modelo o que veio errado
                        messages = [
                            *messages,
                            {"role": "assistant", "content": content[:4000]},
                            {"role": "user", "content": "A resposta não seguiu o formato JSON pedido. "
                             "Responda de novo SOMENTE com o objeto JSON válido, no formato exato do enunciado."},
                        ]
        except httpx.HTTPError as exc:
            self._log(model_name, prompt, tokens_in, tokens_out, started, max(attempts, 1), "error", str(exc)[:500])
            raise LLMError(f"Não foi possível falar com o modelo em {self.base_url}: {exc}") from exc

        self._log(model_name, prompt, tokens_in, tokens_out, started, attempts, "invalid_json", last_error)
        raise LLMError("O modelo respondeu fora do formato esperado duas vezes. Nada foi salvo.", "invalid_json")

    def _log(self, model: str, prompt: Prompt, tin: int, tout: int, started: float, attempts: int,
             status: str, error: str | None = None) -> None:
        self.session.add(
            models.LlmCall(
                model=model,
                prompt_name=prompt.name,
                prompt_version=prompt.version,
                input_tokens=tin or None,
                output_tokens=tout or None,
                latency_ms=int((time.monotonic() - started) * 1000),
                attempts=attempts,
                status=status,
                error=error,
            )
        )
        self.session.commit()
