"""Extraction accuracy for the active provider against hand-labelled notices.

    cd backend && python ../eval/run_eval.py            # LLM_PROVIDER from env, default mock

Notices are looked up in samples/synthetic/ and eval/notices/ (put real notices in
eval/notices/real/ with labels in eval/labels/real/; both folders are git-ignored).
Writes eval/results.md (table quoted in the README) and eval/results.json (raw output).

Scoring, per role and per field:
- strings: equal after trimming and lower-casing
- numbers: equal within 0.01
- deadline: the same instant; joining_date: the same date
- skills and branches: equal as SETS after the product's own normalisation (synonyms)
- selection_process: equal as an ordered list (case-insensitive)
- a null label is only matched by null (this measures "never guess" too)
`notes` is free text and is NOT scored. Roles inside one notice are matched by order.
"""

import json
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import Settings  # noqa: E402
from app.domain.eligibility.branches import default_branches  # noqa: E402
from app.domain.extraction.models import DriveInfo  # noqa: E402
from app.domain.extraction.postprocess import normalise_drive  # noqa: E402
from app.domain.parsing.documents import parse_bytes  # noqa: E402
from app.domain.skills.catalog import default_catalog, skill_key  # noqa: E402
from app.services.extractor_factory import build_extractor  # noqa: E402

EVAL_DIR = ROOT / "eval"
NOTICE_DIRS = [
    ROOT / "samples" / "synthetic",
    EVAL_DIR / "notices" / "synthetic",
    EVAL_DIR / "notices" / "real",
]
LABEL_DIRS = [EVAL_DIR / "labels", EVAL_DIR / "labels" / "real"]
SCORED_FIELDS = [f for f in DriveInfo.model_fields if f != "notes"]


def find_notice(name: str) -> Path:
    for d in NOTICE_DIRS:
        if (d / name).is_file():
            return d / name
    raise FileNotFoundError(f"notice {name} not found in {[str(d) for d in NOTICE_DIRS]}")


def _branch_set(values: list[str] | None) -> set[str] | None:
    if values is None:
        return None
    cat = default_branches()
    return {cat.normalise(v) or v.strip().upper() for v in values}


def _skill_set(values: list[str] | None) -> set[str] | None:
    if values is None:
        return None
    return {skill_key(s) for s in default_catalog().normalise_list(values)}


def same(field: str, expected: Any, got: Any) -> bool:
    if expected is None or got is None:
        return expected is None and got is None
    if field == "eligible_branches":
        return _branch_set(expected) == _branch_set(got)
    if field == "required_skills":
        return _skill_set(expected) == _skill_set(got)
    if field == "eligible_batch":
        return sorted(expected) == sorted(got)
    if field == "selection_process":
        return [s.strip().lower() for s in expected] == [s.strip().lower() for s in got]
    if field == "deadline":
        e = datetime.fromisoformat(str(expected))
        g = got if isinstance(got, datetime) else datetime.fromisoformat(str(got))
        return e.astimezone(timezone.utc) == g.astimezone(timezone.utc)
    if field == "joining_date":
        e = date.fromisoformat(str(expected))
        return e == (got if isinstance(got, date) else date.fromisoformat(str(got)))
    if isinstance(expected, (int, float)) and isinstance(got, (int, float)):
        return abs(float(expected) - float(got)) < 0.01
    return str(expected).strip().lower() == str(got).strip().lower()


def main() -> int:
    provider = os.environ.get("LLM_PROVIDER", "mock")
    settings = Settings(jwt_secret="eval-only-not-used", llm_provider=provider)  # type: ignore[arg-type]
    extractor = build_extractor(settings)

    label_files = sorted(p for d in LABEL_DIRS if d.is_dir() for p in d.glob("*.json"))
    per_field = {f: [0, 0] for f in SCORED_FIELDS}  # correct, total
    roles_total = roles_exact = 0
    providers_used: dict[str, int] = {}
    details: list[dict[str, Any]] = []
    by_source: dict[str, list[int]] = {}  # source -> [correct fields, total fields, exact, roles]
    started = time.perf_counter()

    for label_file in label_files:
        label = json.loads(label_file.read_text(encoding="utf-8"))
        notice = find_notice(label["notice"])
        parsed = parse_bytes(notice.name, notice.read_bytes())
        expected_roles = label["roles"]
        if len(parsed.role_blocks) != len(expected_roles):
            print(f"WARNING {notice.name}: {len(parsed.role_blocks)} roles parsed, "
                  f"{len(expected_roles)} labelled")
        for i, expected in enumerate(expected_roles):
            roles_total += 1
            if i < len(parsed.role_blocks):
                result = extractor.run(parsed.role_blocks[i])
                got = normalise_drive(result.info).model_dump()
                providers_used[result.provider] = providers_used.get(result.provider, 0) + 1
            else:
                got = DriveInfo().model_dump()
            wrong = []
            for field in SCORED_FIELDS:
                ok = same(field, expected.get(field), got.get(field))
                per_field[field][0] += int(ok)
                per_field[field][1] += 1
                if not ok:
                    wrong.append({"field": field, "expected": expected.get(field),
                                  "got": got.get(field)})
            roles_exact += int(not wrong)
            src = by_source.setdefault(label.get("source", "unknown"), [0, 0, 0, 0])
            src[0] += len(SCORED_FIELDS) - len(wrong)
            src[1] += len(SCORED_FIELDS)
            src[2] += int(not wrong)
            src[3] += 1
            details.append({"notice": notice.name, "source": label.get("source", "unknown"),
                            "role_index": i, "errors": wrong})

    elapsed = time.perf_counter() - started
    correct = sum(c for c, _ in per_field.values())
    total = sum(t for _, t in per_field.values())
    summary = {
        "provider_requested": provider,
        "providers_used": providers_used,
        "notices": len(label_files),
        "roles": roles_total,
        "sources": sorted({d["source"] for d in details}),
        "field_accuracy": round(correct / total, 4) if total else None,
        "exact_match_rate": round(roles_exact / roles_total, 4) if roles_total else None,
        "per_field_accuracy": {f: round(c / t, 4) for f, (c, t) in per_field.items() if t},
        "by_source": {
            name: {"roles": r, "field_accuracy": round(c / t, 4), "fields": f"{c}/{t}",
                   "exact_match_rate": round(e / r, 4), "exact": f"{e}/{r}"}
            for name, (c, t, e, r) in sorted(by_source.items())
        },
        "seconds": round(elapsed, 2),
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (EVAL_DIR / "results.json").write_text(
        json.dumps({"summary": summary, "details": details}, indent=2, default=str) + "\n",
        encoding="utf-8")
    write_markdown(summary, details)

    print(f"provider={provider} used={providers_used} notices={len(label_files)} "
          f"roles={roles_total}")
    for f, acc in summary["per_field_accuracy"].items():
        print(f"  {f:<22} {acc:.2%}")
    print(f"field accuracy   : {summary['field_accuracy']:.2%} ({correct}/{total})")
    print(f"exact-match rate : {summary['exact_match_rate']:.2%} ({roles_exact}/{roles_total})")
    for name, b in summary["by_source"].items():
        print(f"  [{name}] roles={b['roles']} field accuracy={b['field_accuracy']:.2%} "
              f"({b['fields']}) exact-match={b['exact_match_rate']:.2%} ({b['exact']})")
    return 0


def write_markdown(summary: dict[str, Any], details: list[dict[str, Any]]) -> None:
    rows = "\n".join(f"| `{f}` | {acc:.1%} |" for f, acc in summary["per_field_accuracy"].items())
    errors = [f"- `{d['notice']}` role {d['role_index']}: `{e['field']}` expected "
              f"`{e['expected']}`, got `{e['got']}`" for d in details for e in d["errors"]]
    by_source = chr(10).join(
        f"| `{n}` | {b['roles']} | {b['field_accuracy']:.1%} ({b['fields']}) | "
        f"{b['exact_match_rate']:.1%} ({b['exact']}) |" for n, b in summary["by_source"].items())
    synthetic_only = all(s.startswith("synthetic") for s in summary["sources"])
    caveat = (
        "> **All notices in this run are SYNTHETIC** and were written by the same person who "
        "wrote the rule-based extractor. Treat these numbers as a regression check, not as "
        "real-world accuracy. Real-world accuracy: **TBD** (add real notices to "
        "`eval/notices/real/` with labels in `eval/labels/real/`)."
        if synthetic_only else
        f"> Sources in this run: {', '.join(summary['sources'])}."
    )
    md = f"""# Extraction evaluation results

Generated by `eval/run_eval.py`. Do not edit by hand.

Reproduce: `cd backend && python ../eval/run_eval.py` (or `make eval`)

{caveat}

| Metric | Value |
|---|---|
| Provider requested | `{summary['provider_requested']}` |
| Providers used | `{summary['providers_used']}` |
| Notices / roles | {summary['notices']} / {summary['roles']} |
| Field accuracy ({len(summary['per_field_accuracy'])} scored fields per role) | {summary['field_accuracy']:.1%} |
| Exact-match rate (every scored field right) | {summary['exact_match_rate']:.1%} |
| Run time | {summary['seconds']} s |
| Run at (UTC) | {summary['run_at']} |

## By source

`synthetic` = the sample notices the rules were developed against (in-sample).
`synthetic-heldout` = written in a different style after the rules; rules not tuned on it.

| Source | Roles | Field accuracy | Exact-match rate |
|---|---|---|---|
{by_source}

## Per-field accuracy

| Field | Accuracy |
|---|---|
{rows}

## Errors

{chr(10).join(errors) if errors else "None in this run."}
"""
    (EVAL_DIR / "results.md").write_text(md, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
