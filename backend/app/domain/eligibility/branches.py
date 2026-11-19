"""Branch names, synonyms and groups ("Computer Science or equivalent", "circuit branches")."""

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parents[3] / "data" / "branches.json"

ANY = "ANY"


def _key(value: str) -> str:
    value = value.lower().replace("&", " and ")
    value = re.sub("[.\u2013\u2014]", " ", value)  # dots, en dash, em dash
    return re.sub(r"\s+", " ", value).strip(" ,;:")


@dataclass(frozen=True)
class BranchCatalog:
    synonyms: dict[str, str]  # normalised phrase -> code
    specialisation_of: dict[str, str]
    groups: dict[str, frozenset[str]]  # group code -> member codes (empty for ANY)
    group_phrases: dict[str, str]  # normalised phrase -> group code

    def normalise(self, raw: str) -> str | None:
        """Branch or group code for a raw string, or None if unknown."""
        if raw.strip().upper() in self.groups:
            return raw.strip().upper()
        key = _key(raw)
        return self.group_phrases.get(key) or self.synonyms.get(key)

    def phrases(self) -> list[tuple[str, str]]:
        """(phrase, code) pairs, longest first, for searching free text."""
        pairs = list(self.synonyms.items()) + list(self.group_phrases.items())
        return sorted(pairs, key=lambda p: len(p[0]), reverse=True)

    def accepts(self, allowed_code: str, student_code: str) -> tuple[bool, str | None]:
        """Does an allowed code accept the student's branch? Returns (ok, explanation)."""
        if allowed_code == ANY:
            return True, "open to all branches"
        if allowed_code == student_code:
            return True, None
        members = self.groups.get(allowed_code)
        if members and student_code in members:
            return True, f"{student_code} is within {allowed_code}"
        if self.specialisation_of.get(student_code) == allowed_code:
            return True, f"{student_code} counted as a specialisation of {allowed_code}"
        return False, None


@lru_cache
def default_branches() -> BranchCatalog:
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    synonyms: dict[str, str] = {}
    for code, names in raw["branches"].items():
        for name in [code, *names]:
            synonyms[_key(name)] = code
    groups: dict[str, frozenset[str]] = {}
    group_phrases: dict[str, str] = {}
    for code, spec in raw["groups"].items():
        groups[code] = frozenset(spec["members"])
        for phrase in spec["phrases"]:
            group_phrases[_key(phrase)] = code
    return BranchCatalog(
        synonyms=synonyms,
        specialisation_of=dict(raw["specialisation_of"]),
        groups=groups,
        group_phrases=group_phrases,
    )
