"""Prompts versionados em backend/prompts/<nome>.<versão>.md (CLAUDE.md: regras de IA).

Cada arquivo tem um cabeçalho com `name` e `version`. Mudar um prompt = criar
um arquivo novo com outra versão; a versão em uso é a mais recente.
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"
_HEADER = re.compile(r"^---\n(.*?)\n---\n", re.S)


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    template: str

    def render(self, **values: object) -> str:
        # Substituição simples: o template tem JSON com chaves, então str.format não serve
        text = self.template
        for key, value in values.items():
            text = text.replace("{" + key + "}", str(value))
        return text


def _parse(path: Path) -> Prompt:
    raw = path.read_text(encoding="utf-8")
    match = _HEADER.match(raw)
    if not match:
        raise ValueError(f"Prompt sem cabeçalho: {path.name}")
    meta = dict(line.split(":", 1) for line in match.group(1).splitlines() if ":" in line)
    meta = {k.strip(): v.strip() for k, v in meta.items()}
    return Prompt(name=meta["name"], version=meta["version"], template=raw[match.end():].strip())


def _version_key(version: str) -> int:
    return int(version.lstrip("v"))


@lru_cache
def load(name: str) -> Prompt:
    """Versão mais recente do prompt `name`."""
    candidates = [_parse(p) for p in PROMPTS_DIR.glob(f"{name}.v*.md")]
    if not candidates:
        raise FileNotFoundError(f"Prompt não encontrado: {name}")
    return max(candidates, key=lambda p: _version_key(p.version))
