import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useAnalytics } from "../api/hooks";
import { ErrorBox } from "../components/Layout";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="card">
      <p className="text-xs uppercase text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}

export function AnalyticsPage() {
  const { skills, summary } = useAnalytics();
  const s = summary.data;

  return (
    <section className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Placement analytics</h1>
        <p className="text-sm text-slate-600">
          Aggregated across all uploaded notices. Duplicate uploads of the same notice are counted
          once. No student data is shown.
        </p>
      </div>
      <ErrorBox error={skills.error ?? summary.error} />
      {s && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Drives" value={String(s.total_drives)} />
          <Stat label="Companies" value={String(s.total_companies)} />
          <Stat
            label="Median CTC"
            value={s.median_ctc_lpa === null ? "n/a" : `${s.median_ctc_lpa} LPA`}
          />
          <Stat label="Drives with a bond" value={`${s.drives_with_bond} / ${s.total_drives}`} />
        </div>
      )}
      <div className="card">
        <h2 className="mb-3 font-semibold">Top requested skills</h2>
        {skills.data && skills.data.top_skills.length === 0 && (
          <p className="text-sm text-slate-500">No skills extracted yet.</p>
        )}
        {skills.data && skills.data.top_skills.length > 0 && (
          <div
            data-testid="skills-chart"
            // One row per skill so every label fits (up to 20 skills).
            style={{ height: Math.max(240, skills.data.top_skills.length * 30) }}
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={skills.data.top_skills} layout="vertical" margin={{ left: 40 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" allowDecimals={false} />
                <YAxis type="category" dataKey="skill" width={140} interval={0} />
                <Tooltip />
                <Bar dataKey="count" fill="#4f46e5" name="Drives" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
      {s && (
        <div className="card">
          <h2 className="mb-3 font-semibold">Drives by role type</h2>
          <ul className="divide-y divide-slate-100 text-sm">
            {s.drives_by_role_category.map((r) => (
              <li key={r.role_category} className="flex justify-between py-2">
                <span>{r.role_category}</span>
                <span className="font-medium">{r.count}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
