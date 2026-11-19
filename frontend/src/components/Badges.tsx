import type { Eligibility } from "../api/schemas";
import { formatPercent } from "../lib/format";

const ELIGIBILITY_STYLE: Record<Eligibility, { label: string; cls: string }> = {
  eligible: { label: "Eligible", cls: "bg-emerald-100 text-emerald-800" },
  not_eligible: { label: "Not eligible", cls: "bg-rose-100 text-rose-800" },
  unknown: { label: "Check manually", cls: "bg-amber-100 text-amber-800" },
};

export function EligibilityBadge({ value }: { value: Eligibility }) {
  const s = ELIGIBILITY_STYLE[value];
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${s.cls}`}>{s.label}</span>;
}

export function DeadlineBadge({ closesSoon, closed }: { closesSoon: boolean; closed: boolean }) {
  if (closed) {
    return (
      <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-600">
        Closed
      </span>
    );
  }
  if (!closesSoon) return null;
  return (
    <span className="rounded-full bg-red-600 px-2 py-0.5 text-xs font-semibold text-white">
      Closes in &lt; 24h
    </span>
  );
}

export function MatchBadge({ score }: { score: number | null }) {
  const pct = score === null ? null : Math.round(score * 100);
  const cls =
    pct === null
      ? "bg-slate-100 text-slate-600"
      : pct >= 70
        ? "bg-emerald-100 text-emerald-800"
        : pct >= 40
          ? "bg-amber-100 text-amber-800"
          : "bg-rose-100 text-rose-800";
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}
      title={score === null ? "Notice lists no skills" : undefined}
    >
      {formatPercent(score)} match
    </span>
  );
}

export function SkillChips({ skills, kind }: { skills: string[]; kind: "matched" | "missing" }) {
  if (!skills.length) return <p className="text-sm text-slate-500">None</p>;
  const cls =
    kind === "matched"
      ? "bg-emerald-50 text-emerald-800 ring-emerald-200"
      : "bg-rose-50 text-rose-800 ring-rose-200";
  return (
    <ul className="flex flex-wrap gap-2" aria-label={`${kind} skills`}>
      {skills.map((s) => (
        <li key={s} className={`rounded-full px-2.5 py-1 text-xs ring-1 ${cls}`}>
          {s}
        </li>
      ))}
    </ul>
  );
}
