"""Skill dictionary: canonical names, synonyms and normalisation.

"JS", "javascript" and "Java Script" all normalise to "JavaScript". Skills that are not in
the dictionary are kept as the user typed them (trimmed), so matching still works for them.
"""

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[3] / "data"


@dataclass(frozen=True)
class SkillEntry:
    name: str
    aliases: tuple[str, ...] = ()
    normalise_only: tuple[str, ...] = ()
    strict: bool = False

    @property
    def detect_forms(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)


def skill_key(value: str) -> str:
    """Case/whitespace-insensitive key: ' Node.JS ' -> 'node.js'."""
    return re.sub(r"\s+", " ", value).strip().strip(".,;:").lower()


def compact_key(value: str) -> str:
    """Looser key that also ignores dots, dashes and spaces: 'Node.js' -> 'nodejs'."""
    return re.sub(r"[^a-z0-9+#]", "", skill_key(value))


class SkillCatalog:
    def __init__(self, entries: Iterable[SkillEntry]) -> None:
        self.entries: tuple[SkillEntry, ...] = tuple(entries)
        self._by_key: dict[str, str] = {}
        compact: dict[str, set[str]] = {}
        for entry in self.entries:
            for form in (entry.name, *entry.aliases, *entry.normalise_only):
                key = skill_key(form)
                existing = self._by_key.get(key)
                if existing is not None and existing != entry.name:
                    raise ValueError(f"skill form {form!r} maps to {existing} and {entry.name}")
                self._by_key[key] = entry.name
                compact.setdefault(compact_key(form), set()).add(entry.name)
        # Only keep loose keys that point to exactly one skill.
        self._by_compact = {k: next(iter(v)) for k, v in compact.items() if len(v) == 1 and k}

    @classmethod
    def from_file(cls, path: Path) -> "SkillCatalog":
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            SkillEntry(
                name=item["name"],
                aliases=tuple(item.get("aliases", [])),
                normalise_only=tuple(item.get("normalise_only", [])),
                strict=bool(item.get("strict", False)),
            )
            for item in raw
        )

    def canonical(self, raw: str) -> str | None:
        key = skill_key(raw)
        if not key:
            return None
        return self._by_key.get(key) or self._by_compact.get(compact_key(raw))

    def normalise(self, raw: str) -> str:
        """Canonical name if known, otherwise the cleaned input."""
        return self.canonical(raw) or re.sub(r"\s+", " ", raw).strip().strip(".,;:")

    def normalise_list(self, raws: Iterable[str]) -> list[str]:
        """Normalise and de-duplicate (case-insensitive), keeping first-seen order."""
        seen: set[str] = set()
        out: list[str] = []
        for raw in raws:
            name = self.normalise(raw)
            key = skill_key(name)
            if key and key not in seen:
                seen.add(key)
                out.append(name)
        return out


@lru_cache
def default_catalog() -> SkillCatalog:
    return SkillCatalog.from_file(DATA_DIR / "skills.json")
