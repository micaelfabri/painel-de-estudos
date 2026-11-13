"""Motor genérico de regras de avaliação.

A regra de cada disciplina é um dado JSON (CLAUDE.md: regras de avaliação são
dados, nunca `if` por disciplina). Formato:

{
  "label": "Padrão de exemplo (planos de ensino 2026)",
  "pass_min": 6,
  "max_total": 10,
  "parts": [
    {"key": "av", "label": "AV/AVS", "max": 8},
    {"key": "pa", "label": "Progresso Acadêmico", "max": 2,
     "counts_if": {"part": "av", "gte": 4}}            # opcional
  ],
  "min_attendance": 0.75,                               # opcional
  "in_person": true,                                    # opcional
  "to_check": false,                                    # regra ainda a confirmar
  "source": "texto livre com a fonte"
}
"""

from typing import Any

from pydantic import BaseModel, Field


class RulePart(BaseModel):
    key: str
    label: str
    max: float
    counts_if: dict[str, Any] | None = None
    # v1.5: de onde vem a nota prevista: "exam" (melhor nota de prova) | "mocks" (soma dos simulados)
    source: str | None = None


class GradingRule(BaseModel):
    label: str
    pass_min: float = 6
    max_total: float = 10
    parts: list[RulePart] = Field(min_length=1)
    min_attendance: float | None = None
    in_person: bool = False
    to_check: bool = False
    source: str | None = None


class GradeInput(BaseModel):
    scores: dict[str, float] = Field(default_factory=dict)
    attendance: float | None = None


class GradeResult(BaseModel):
    total: float
    counted: dict[str, float]
    ignored: list[str]
    passed: bool | None
    reasons: list[str]
    missing: list[str]


def evaluate(rule: GradingRule, data: GradeInput) -> GradeResult:
    counted: dict[str, float] = {}
    ignored: list[str] = []
    missing: list[str] = []
    reasons: list[str] = []

    for part in rule.parts:
        if part.key not in data.scores:
            missing.append(part.key)
            continue
        value = data.scores[part.key]
        if value < 0 or value > part.max:
            raise ValueError(f"{part.label}: nota {value} fora de 0–{part.max}")
        if part.counts_if:
            ref = data.scores.get(part.counts_if["part"])
            limit = part.counts_if.get("gte")
            if ref is None or limit is None or ref < limit:
                ignored.append(part.key)
                reasons.append(f"{part.label} só soma com {part.counts_if['part']} ≥ {limit}")
                continue
        counted[part.key] = value

    total = round(min(sum(counted.values()), rule.max_total), 2)

    passed: bool | None
    if missing:
        passed = None
        reasons.append("faltam notas: " + ", ".join(missing))
    else:
        passed = total >= rule.pass_min
        if not passed:
            reasons.append(f"total {total} abaixo de {rule.pass_min}")

    if rule.min_attendance is not None:
        if data.attendance is None:
            passed = None if passed else passed
            reasons.append(f"frequência mínima de {rule.min_attendance:.0%} não informada")
        elif data.attendance < rule.min_attendance:
            passed = False
            reasons.append(f"frequência {data.attendance:.0%} abaixo de {rule.min_attendance:.0%}")

    return GradeResult(total=total, counted=counted, ignored=ignored, passed=passed, reasons=reasons, missing=missing)


# --- Nota prevista (v1.5, D30) -----------------------------------------------

# Parte sem "source" na regra: AV/AVS vem das provas, Progresso Acadêmico dos simulados (SPEC §5)
DEFAULT_SOURCE = {"av": "exam", "pa": "mocks"}
SOURCE_LABELS = {"exam": "nota da prova", "mocks": "soma dos simulados"}


def predict(rule: GradingRule, exam_scores: list[float], mock_scores: list[float | None]) -> dict:
    """Nota prevista com o que já foi lançado; diz quanto falta na prova para passar.

    exam_scores: notas de prova lançadas (vale a maior, AV ou AVS); mock_scores: um item por simulado
    (None = ainda sem nota).
    """
    scores: dict[str, float] = {}
    parts = []
    for part in rule.parts:
        source = part.source or DEFAULT_SOURCE.get(part.key)
        value: float | None = None
        pending = 0
        if source == "exam" and exam_scores:
            value = min(max(exam_scores), part.max)
        elif source == "mocks" and mock_scores:
            done = [v for v in mock_scores if v is not None]
            pending = len(mock_scores) - len(done)
            # Simulado sem nota conta 0 por enquanto (previsão conservadora); "pending" avisa quantos faltam
            value = min(round(sum(done), 2), part.max)
        if value is not None:
            scores[part.key] = value
        parts.append({"key": part.key, "label": part.label, "max": part.max, "value": value,
                      "source": source, "source_label": SOURCE_LABELS.get(source or "", "lançar à mão"),
                      "pending": pending})

    missing = [p for p in parts if p["value"] is None]
    out: dict[str, Any] = {"label": rule.label, "to_check": rule.to_check, "pass_min": rule.pass_min,
                           "max_total": rule.max_total, "parts": parts, "total": None, "passed": None,
                           "needed": None, "known_total": round(sum(scores.values()), 2)}
    if not missing:
        result = evaluate(rule, GradeInput(scores=scores))
        out["total"], out["passed"] = result.total, result.total >= rule.pass_min
        return out
    # Quanto falta: menor nota na prova (única parte faltando) que faz passar, em passos de 0,1
    exam_missing = [p for p in missing if p["source"] == "exam"]
    if len(missing) == 1 and exam_missing:
        part = exam_missing[0]
        steps = int(round(part["max"] * 10))
        for i in range(steps + 1):
            trial = {**scores, part["key"]: i / 10}
            if evaluate(rule, GradeInput(scores=trial)).total >= rule.pass_min:
                out["needed"] = {"key": part["key"], "label": part["label"], "value": i / 10, "possible": True}
                break
        else:
            out["needed"] = {"key": part["key"], "label": part["label"], "value": None, "possible": False}
    return out


# Modelos de regra conhecidos (SPEC §5). Ficam disponíveis no modo Gerenciar.
PRESETS: dict[str, dict] = {
    "padrao_2026": {
        "label": "Padrão de exemplo (planos de ensino 2026)",
        "pass_min": 6,
        "max_total": 10,
        "parts": [
            {"key": "av", "label": "AV/AVS", "max": 8},
            {"key": "pa", "label": "Progresso Acadêmico", "max": 2},
        ],
        "to_check": True,
        "source": "Planos de ensino 2026. O e-book de jan/2024 descreve AV 0–10 + AVAs até +2; a confirmar qual vale.",
    },
    "padroes_java": {
        "label": "Padrões de Projeto",
        "pass_min": 6,
        "max_total": 10,
        "parts": [{"key": "av", "label": "AV/AVS", "max": 10}],
        "min_attendance": 0.75,
        "in_person": True,
        "source": "Plano de ensino 2026: AV/AVS 0–10, presenciais, 75% de frequência.",
    },
    "arquitetura_sistemas": {
        "label": "Arquitetura de Sistemas",
        "pass_min": 6,
        "max_total": 10,
        "parts": [
            {"key": "av", "label": "AV/AVS", "max": 10},
            {"key": "ap", "label": "AP", "max": 2, "counts_if": {"part": "av", "gte": 4}},
        ],
        "source": "Plano de ensino 2026: AV/AVS 0–10 + AP 0–2, que só soma com AV/AVS ≥ 4.",
    },
    "extensionista": {
        "label": "Extensionista (regra própria)",
        "pass_min": 6,
        "max_total": 10,
        "parts": [
            {"key": "av", "label": "AV/AVS", "max": 8},
            {"key": "ext", "label": "Atividade de extensão", "max": 2},
        ],
        "to_check": True,
        "source": "Extensionistas: atividade de extensão de 2 pontos + simulados. Divisão exata a confirmar.",
    },
}
