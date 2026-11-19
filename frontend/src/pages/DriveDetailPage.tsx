import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useDeleteDrive, useDrive, useEditDrive, useUpdateStatus } from "../api/hooks";
import { DRIVE_STATUSES, type Drive, type DriveInfo, type DriveStatus } from "../api/schemas";
import { DeadlineBadge, EligibilityBadge, MatchBadge, SkillChips } from "../components/Badges";
import { ErrorBox } from "../components/Layout";
import {
  formatCtc,
  formatDeadline,
  formatInr,
  fromIstLocalInput,
  splitList,
  toIstLocalInput,
} from "../lib/format";

const RULE_LABELS: Record<string, string> = {
  cgpa: "CGPA",
  ug_percent: "UG percentage",
  pct_10: "Class X",
  pct_12: "Class XII",
  backlogs: "Active backlogs",
  branch: "Branch",
  batch: "Batch",
};

const RULE_ICON = { pass: "✔", fail: "✘", unknown: "?", not_specified: "–" } as const;
const RULE_CLS = {
  pass: "text-emerald-700",
  fail: "text-rose-700",
  unknown: "text-amber-700",
  not_specified: "text-slate-400",
} as const;

export function DriveDetailPage() {
  const { id = "" } = useParams();
  const drive = useDrive(id);
  const [editing, setEditing] = useState(false);

  if (drive.isLoading) return <p className="text-sm text-slate-500">Loading...</p>;
  if (drive.error || !drive.data) return <ErrorBox error={drive.error ?? new Error("Not found")} />;
  const d = drive.data;

  return (
    <section className="space-y-4">
      <Header drive={d} />
      <div className="grid gap-4 md:grid-cols-2">
        <div className="card space-y-3">
          <h2 className="font-semibold">Eligibility</h2>
          <ul className="space-y-2" aria-label="eligibility checklist">
            {d.eligibility_reasons.map((r) => (
              <li key={r.rule} className="flex gap-2 text-sm">
                <span className={`w-4 font-bold ${RULE_CLS[r.status]}`} aria-label={r.status}>
                  {RULE_ICON[r.status]}
                </span>
                <span>
                  <span className="font-medium">{RULE_LABELS[r.rule] ?? r.rule}:</span> {r.reason}
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div className="card space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Skills</h2>
            <MatchBadge score={d.match_score} />
          </div>
          <h3 className="text-sm font-medium text-slate-600">You have</h3>
          <SkillChips skills={d.matched_skills} kind="matched" />
          <h3 className="text-sm font-medium text-slate-600">Missing</h3>
          <SkillChips skills={d.missing_skills} kind="missing" />
        </div>
      </div>
      <div className="card">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-semibold">Extracted details</h2>
          {!editing && (
            <button type="button" className="btn-secondary" onClick={() => setEditing(true)}>
              Edit if wrong
            </button>
          )}
        </div>
        {editing ? (
          <EditForm drive={d} onDone={() => setEditing(false)} />
        ) : (
          <Details info={d.info} />
        )}
        <p className="mt-3 text-xs text-slate-500">
          Extracted by: {d.extraction_provider}
          {d.source_filename ? ` from ${d.source_filename}` : " from pasted text"}. Always verify
          with the original notice.
        </p>
      </div>
    </section>
  );
}

function Header({ drive }: { drive: Drive }) {
  const update = useUpdateStatus();
  const del = useDeleteDrive();
  const navigate = useNavigate();
  return (
    <div className="card flex flex-wrap items-start justify-between gap-4">
      <div className="space-y-1">
        <h1 className="text-xl font-semibold">{drive.info.company ?? "Unknown company"}</h1>
        <p className="text-slate-600">{drive.info.role ?? "Role not stated"}</p>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <EligibilityBadge value={drive.eligibility} />
          <span>Deadline: {formatDeadline(drive.info.deadline)}</span>
          <DeadlineBadge closesSoon={drive.closes_within_24h} closed={drive.is_closed} />
        </div>
      </div>
      <div className="flex items-end gap-2">
        <div>
          <label className="label" htmlFor="status">
            My status
          </label>
          <select
            id="status"
            className="input"
            value={drive.status}
            onChange={(e) => update.mutate({ id: drive.id, status: e.target.value as DriveStatus })}
          >
            {DRIVE_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          className="btn-secondary text-rose-700"
          onClick={() => {
            if (window.confirm("Delete this drive? This cannot be undone.")) {
              del.mutate(drive.id, { onSuccess: () => navigate("/") });
            }
          }}
        >
          Delete
        </button>
      </div>
      <ErrorBox error={update.error ?? del.error} />
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-3 gap-2 py-1.5 text-sm">
      <dt className="text-slate-500">{label}</dt>
      <dd className="col-span-2">{value}</dd>
    </div>
  );
}

const show = (v: string | number | null | undefined, suffix = "") =>
  v === null || v === undefined || v === "" ? "Not stated" : `${v}${suffix}`;
const list = (v: (string | number)[] | null) => (v && v.length ? v.join(", ") : "Not stated");

function Details({ info }: { info: DriveInfo }) {
  return (
    <dl className="divide-y divide-slate-100">
      <Row label="Location" value={show(info.location)} />
      <Row label="CTC" value={formatCtc(info.ctc_lpa_min, info.ctc_lpa_max)} />
      <Row label="Stipend / month" value={info.stipend_per_month === null ? "Not stated" : formatInr(info.stipend_per_month)} />
      <Row label="Joining date" value={show(info.joining_date)} />
      <Row label="Bond" value={info.bond_years === null ? "Not stated" : info.bond_years === 0 ? "No bond" : `${info.bond_years} years`} />
      <Row label="Bond penalty" value={info.bond_penalty_inr === null ? "Not stated" : formatInr(info.bond_penalty_inr)} />
      <Row label="Min CGPA" value={show(info.min_cgpa)} />
      <Row label="Min UG %" value={show(info.min_ug_percent, "%")} />
      <Row label="Min Class X %" value={show(info.min_percent_10th, "%")} />
      <Row label="Min Class XII %" value={show(info.min_percent_12th, "%")} />
      <Row label="Max active backlogs" value={show(info.max_active_backlogs)} />
      <Row label="Branches" value={list(info.eligible_branches)} />
      <Row label="Batch" value={list(info.eligible_batch)} />
      <Row label="Required skills" value={list(info.required_skills)} />
      <Row label="Selection process" value={list(info.selection_process)} />
      <Row label="Notes" value={show(info.notes)} />
    </dl>
  );
}

type FieldKind = "text" | "number" | "list" | "numlist" | "date" | "datetime";
const FIELDS: { key: keyof DriveInfo; label: string; kind: FieldKind }[] = [
  { key: "company", label: "Company", kind: "text" },
  { key: "role", label: "Role", kind: "text" },
  { key: "location", label: "Location", kind: "text" },
  { key: "deadline", label: "Deadline (IST)", kind: "datetime" },
  { key: "ctc_lpa_min", label: "CTC min (LPA)", kind: "number" },
  { key: "ctc_lpa_max", label: "CTC max (LPA)", kind: "number" },
  { key: "stipend_per_month", label: "Stipend / month (INR)", kind: "number" },
  { key: "joining_date", label: "Joining date", kind: "date" },
  { key: "bond_years", label: "Bond (years)", kind: "number" },
  { key: "bond_penalty_inr", label: "Bond penalty (INR)", kind: "number" },
  { key: "min_cgpa", label: "Min CGPA", kind: "number" },
  { key: "min_ug_percent", label: "Min UG %", kind: "number" },
  { key: "min_percent_10th", label: "Min Class X %", kind: "number" },
  { key: "min_percent_12th", label: "Min Class XII %", kind: "number" },
  { key: "max_active_backlogs", label: "Max active backlogs", kind: "number" },
  { key: "eligible_branches", label: "Branches (comma separated)", kind: "list" },
  { key: "eligible_batch", label: "Batch years (comma separated)", kind: "numlist" },
  { key: "required_skills", label: "Required skills (comma separated)", kind: "list" },
  { key: "selection_process", label: "Selection rounds (comma separated)", kind: "list" },
  { key: "notes", label: "Notes", kind: "text" },
];

function toInput(info: DriveInfo, key: keyof DriveInfo, kind: FieldKind): string {
  const v = info[key];
  if (v === null) return "";
  if (kind === "datetime") return toIstLocalInput(v as string);
  if (Array.isArray(v)) return v.join(", ");
  return String(v);
}

function fromInput(raw: string, kind: FieldKind): DriveInfo[keyof DriveInfo] {
  const value = raw.trim();
  if (!value) return null;
  switch (kind) {
    case "number":
      return Number(value);
    case "list":
      return splitList(value);
    case "numlist":
      return splitList(value)?.map(Number) ?? null;
    case "datetime":
      return fromIstLocalInput(value);
    default:
      return value;
  }
}

function EditForm({ drive, onDone }: { drive: Drive; onDone: () => void }) {
  const edit = useEditDrive();
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(FIELDS.map((f) => [f.key, toInput(drive.info, f.key, f.kind)])),
  );

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const info = { ...drive.info };
    for (const f of FIELDS) {
      (info as Record<string, unknown>)[f.key] = fromInput(values[f.key] ?? "", f.kind);
    }
    edit.mutate({ id: drive.id, info }, { onSuccess: onDone });
  };

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="grid gap-3 md:grid-cols-2">
        {FIELDS.map((f) => (
          <div key={f.key}>
            <label className="label" htmlFor={`edit-${f.key}`}>
              {f.label}
            </label>
            <input
              id={`edit-${f.key}`}
              className="input"
              type={
                f.kind === "number"
                  ? "number"
                  : f.kind === "date"
                    ? "date"
                    : f.kind === "datetime"
                      ? "datetime-local"
                      : "text"
              }
              step={f.kind === "number" ? "any" : undefined}
              value={values[f.key] ?? ""}
              onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}
            />
          </div>
        ))}
      </div>
      <ErrorBox error={edit.error} />
      <div className="flex gap-2">
        <button type="submit" className="btn" disabled={edit.isPending}>
          Save and recheck eligibility
        </button>
        <button type="button" className="btn-secondary" onClick={onDone}>
          Cancel
        </button>
      </div>
    </form>
  );
}
