"""F0 — teste de modelos (SPEC §7).

Roda no seu PC com o LM Studio (ou Ollama) aberto. Jeito mais simples, dentro do Docker (ver eval/README.md):

    docker compose run --rm -v "${PWD}\\eval:/app/eval" app python /app/eval/run_eval.py --base-url http://host.docker.internal:1234/v1 --options 5 --models qwen/qwen3.5-9b

Ou fora do Docker:

    cd backend
    .venv\\Scripts\\activate            # o mesmo ambiente do README (pip install -r requirements-dev.txt)
    python ..\\eval\\run_eval.py --models qwen3.5:9b gemma4:12b gemma4:e4b --options 5

Mede, para cada modelo × tema em eval/topics/*.txt:
- JSON válido (na 1ª tentativa, depois da nova tentativa, ou nunca), usando o mesmo prompt e o mesmo
  validador do app;
- tempo por resposta e tokens.
Gera eval/results/<data-hora>/ com as respostas e um RESULTS_<data-hora>.md para você dar nota de 1 a 5
ao resumo e às questões. O modelo escolhido vira o padrão em Gerenciar → Configurações.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agent import prompts  # noqa: E402
from app.agent.router import GeneratedSet  # noqa: E402


def make_client(base_url: str, timeout: int):
    """Usa o MESMO cliente do app (formatos json_schema → json_object → sem formato, nova tentativa,
    detecção de resposta cortada), com um banco em memória só para o registro de uso."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    from app import models, settings_store  # noqa: F401  (models registra as tabelas)
    from app.agent.client import LLMClient
    from app.db import Base

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = Session(engine)
    settings_store.put(session, "llm_base_url", base_url)
    settings_store.put(session, "llm_timeout_seconds", timeout)
    return session, LLMClient(session)


def run_one(session, client, model: str, prompt, rendered: str) -> dict:
    from sqlalchemy import select

    from app import models
    from app.agent.client import LLMError

    started = time.monotonic()
    try:
        parsed, _ = client.chat_json(prompt, rendered, GeneratedSet, model=model)
        result = {"valid": True, "result": parsed.model_dump()}
    except LLMError as exc:
        result = {"valid": False, "error": str(exc)}
    call = session.scalars(select(models.LlmCall).order_by(models.LlmCall.id.desc())).first()
    result.update({
        "seconds": round(time.monotonic() - started, 1),
        "attempts": call.attempts if call else 0,
        "tokens_in": (call.input_tokens or 0) if call else 0,
        "tokens_out": (call.output_tokens or 0) if call else 0,
    })
    if call and call.error:
        result["log_error"] = call.error
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="F0: compara modelos locais no estilo de prova do painel")
    parser.add_argument("--base-url", default="http://localhost:11434/v1", help="Ollama: :11434/v1 · LM Studio: :1234/v1")
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--options", type=int, required=True, help="alternativas por questão (confira numa prova real)")
    parser.add_argument("--questions", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=900, help="segundos de espera por resposta (30 a 3600)")
    parser.add_argument("--topics", default=str(ROOT / "eval" / "topics"))
    args = parser.parse_args()

    topics = sorted(p for p in Path(args.topics).glob("*.txt") if not p.name.startswith("EXEMPLO"))
    if not topics:
        print(f"Nenhum tema em {args.topics}. Cole o texto de 3 temas reais em arquivos .txt (veja eval/README.md).")
        return 1

    prompt = prompts.load("generate_questions")
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    out = ROOT / "eval" / "results" / stamp
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    session, client = make_client(args.base_url.rstrip("/"), args.timeout)

    for model in args.models:
        for topic in topics:
            text = topic.read_text(encoding="utf-8").strip()
            rendered = prompt.render(n_questions=args.questions, n_options=args.options, avoid="(nenhuma)",
                                     topic_title=topic.stem, text=text)
            print(f"→ {model} · {topic.stem} … ", end="", flush=True)
            try:
                r = run_one(session, client, model, prompt, rendered)
            except Exception as exc:  # modelo fora do ar, nome errado etc.
                r = {"valid": False, "attempts": 0, "seconds": 0, "tokens_in": 0, "tokens_out": 0, "error": str(exc)}
            print("ok" if r["valid"] else "falhou", f"({r['seconds']} s, tentativas {r['attempts']})")
            safe = model.replace(":", "_").replace("/", "_")
            (out / f"{safe}__{topic.stem}.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
            rows.append((model, topic.stem, r))

    write_report(out, stamp, prompt, args, rows)
    print(f"\nPronto. Abra eval/RESULTS_{stamp}.md, dê as notas e escolha o modelo padrão.")
    return 0


def write_report(out: Path, stamp: str, prompt, args, rows) -> None:
    lines = [f"# F0 — teste de modelos ({stamp})", "",
             f"Prompt: `{prompt.name}.{prompt.version}` · {args.questions} questões · {args.options} alternativas · "
             f"servidor `{args.base_url}`", "",
             "## Números (automático)", "",
             "| Modelo | Tema | JSON válido | Tentativas | Tempo (s) | Tokens entrada/saída |",
             "|---|---|---|---|---|---|"]
    for model, topic, r in rows:
        valid = "sim" if r["valid"] else "não"
        lines.append(f"| {model} | {topic} | {valid} | {r['attempts']} | {r['seconds']} | {r['tokens_in']}/{r['tokens_out']} |")
    lines += ["", "## Notas (1 a 5)", "",
              "Leia cada resumo e as questões abaixo e preencha. Critérios: o resumo está certo e só usa o texto? "
              "As questões parecem de prova? As erradas são plausíveis? A correta está mesmo certa?", "",
              "| Modelo | Tema | Resumo (1–5) | Questões (1–5) | Observação |", "|---|---|---|---|---|"]
    for model, topic, _ in rows:
        lines.append(f"| {model} | {topic} |  |  |  |")
    lines += ["", "## Escolha", "", "Modelo padrão: ", "Por quê: ", "", "---", "", "## Respostas para avaliar", ""]
    for model, topic, r in rows:
        lines.append(f"### {model} · {topic}")
        if not r["valid"]:
            lines += ["", f"Falhou: {r.get('error', '')}", ""]
            continue
        res = r["result"]
        lines += ["", f"**Resumo:** {res['summary']}", ""]
        for i, q in enumerate(res["questions"], 1):
            lines.append(f"{i}. {q['statement']}")
            for j, opt in enumerate(q["options"]):
                mark = " ✅" if j == q["correct_index"] else ""
                lines.append(f"   - {'ABCDEF'[j]}) {opt}{mark}")
            if q.get("explanation"):
                lines.append(f"   - *Explicação:* {q['explanation']}")
        lines.append("")
    (ROOT / "eval" / f"RESULTS_{stamp}.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
