import { useEffect, useState, type FormEvent } from "react";
import { useProfile, useUpdateProfile } from "../api/hooks";
import type { Profile, ProfileUpdate } from "../api/schemas";
import { ErrorBox } from "../components/Layout";
import { splitList } from "../lib/format";

type Form = Record<"name" | "branch" | "batch" | "cgpa" | "pct_10" | "pct_12" | "backlogs" | "skills", string>;

const toForm = (p: Profile): Form => ({
  name: p.name ?? "",
  branch: p.branch ?? "",
  batch: p.batch?.toString() ?? "",
  cgpa: p.cgpa?.toString() ?? "",
  pct_10: p.pct_10?.toString() ?? "",
  pct_12: p.pct_12?.toString() ?? "",
  backlogs: p.backlogs?.toString() ?? "",
  skills: p.skills.join(", "),
});

const num = (v: string) => (v.trim() === "" ? null : Number(v));

function toUpdate(f: Form): ProfileUpdate {
  return {
    name: f.name.trim() || null,
    branch: f.branch.trim() || null,
    batch: num(f.batch),
    cgpa: num(f.cgpa),
    pct_10: num(f.pct_10),
    pct_12: num(f.pct_12),
    backlogs: num(f.backlogs),
    skills: splitList(f.skills) ?? [],
  };
}

export function ProfilePage() {
  const profile = useProfile();
  const save = useUpdateProfile();
  const [form, setForm] = useState<Form | null>(null);

  useEffect(() => {
    if (profile.data) setForm(toForm(profile.data));
  }, [profile.data]);

  if (profile.error) return <ErrorBox error={profile.error} />;
  if (!form) return <p className="text-sm text-slate-500">Loading...</p>;

  const field = (key: keyof Form, label: string, props: Record<string, string | number> = {}) => (
    <div>
      <label className="label" htmlFor={`p-${key}`}>
        {label}
      </label>
      <input
        id={`p-${key}`}
        className="input"
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        {...props}
      />
    </div>
  );

  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate(toUpdate(form));
  };

  return (
    <section className="space-y-4">
      <h1 className="text-xl font-semibold">My profile</h1>
      <p className="text-sm text-slate-600">
        Eligibility for every saved drive is recalculated when you save.
      </p>
      <form onSubmit={submit} className="card grid gap-4 md:grid-cols-2">
        {field("name", "Name")}
        {field("branch", "Branch (e.g. CSE, IT, CSE-IT, ECE)")}
        {field("batch", "Batch (graduation year)", { type: "number", min: 2000, max: 2100 })}
        {field("cgpa", "CGPA (0-10)", { type: "number", step: "0.01", min: 0, max: 10 })}
        {field("pct_10", "Class X %", { type: "number", step: "0.01", min: 0, max: 100 })}
        {field("pct_12", "Class XII % (or diploma)", { type: "number", step: "0.01", min: 0, max: 100 })}
        {field("backlogs", "Active backlogs", { type: "number", min: 0, max: 50 })}
        <div className="md:col-span-2">{field("skills", "Skills (comma separated)")}</div>
        <div className="flex items-center gap-3 md:col-span-2">
          <button type="submit" className="btn" disabled={save.isPending}>
            Save profile
          </button>
          {save.isSuccess && <span className="text-sm text-emerald-700">Saved.</span>}
        </div>
        <div className="md:col-span-2">
          <ErrorBox error={save.error} />
        </div>
      </form>
    </section>
  );
}
