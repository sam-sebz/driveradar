import { useState } from "react";
import { Link } from "react-router-dom";
import { useDrives, type DriveFilters } from "../api/hooks";
import { DRIVE_STATUSES, type DriveStatus } from "../api/schemas";
import { DeadlineBadge, EligibilityBadge, MatchBadge } from "../components/Badges";
import { ErrorBox } from "../components/Layout";
import { formatCtc, formatDeadline } from "../lib/format";

export function DashboardPage() {
  const [filters, setFilters] = useState<DriveFilters>({});
  const drives = useDrives(filters);

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">My drives</h1>
          <p className="text-sm text-slate-600">Sorted by deadline, soonest first.</p>
        </div>
        <Link to="/upload" className="btn">
          Upload a notice
        </Link>
      </div>

      <div className="card flex flex-wrap items-end gap-4 py-3">
        <div>
          <label className="label" htmlFor="f-status">
            Status
          </label>
          <select
            id="f-status"
            className="input"
            value={filters.status ?? ""}
            onChange={(e) => setFilters({ ...filters, status: e.target.value as DriveStatus | "" })}
          >
            <option value="">All</option>
            {DRIVE_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="f-elig">
            Eligibility
          </label>
          <select
            id="f-elig"
            className="input"
            value={filters.eligibility ?? ""}
            onChange={(e) => setFilters({ ...filters, eligibility: e.target.value })}
          >
            <option value="">All</option>
            <option value="eligible">Eligible</option>
            <option value="not_eligible">Not eligible</option>
            <option value="unknown">Check manually</option>
          </select>
        </div>
        <label className="flex items-center gap-2 pb-2 text-sm">
          <input
            type="checkbox"
            checked={filters.closingSoon ?? false}
            onChange={(e) => setFilters({ ...filters, closingSoon: e.target.checked })}
          />
          Closing in 24h
        </label>
      </div>

      <ErrorBox error={drives.error} />
      {drives.isLoading && <p className="text-sm text-slate-500">Loading...</p>}
      {drives.data && drives.data.length === 0 && (
        <div className="card text-center text-sm text-slate-600">
          No drives yet. <Link to="/upload" className="text-indigo-700 underline">Upload a notice</Link> to get started.
        </div>
      )}
      {drives.data && drives.data.length > 0 && (
        <div className="card overflow-x-auto p-0">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Company / role</th>
                <th className="px-4 py-3">Deadline</th>
                <th className="px-4 py-3">CTC</th>
                <th className="px-4 py-3">Eligibility</th>
                <th className="px-4 py-3">Skills</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {drives.data.map((d) => (
                <tr key={d.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <Link to={`/drives/${d.id}`} className="font-medium text-indigo-700 hover:underline">
                      {d.info.company ?? "Unknown company"}
                    </Link>
                    <div className="text-slate-600">{d.info.role ?? "Role not stated"}</div>
                  </td>
                  <td className="px-4 py-3">
                    <div>{formatDeadline(d.info.deadline)}</div>
                    <DeadlineBadge closesSoon={d.closes_within_24h} closed={d.is_closed} />
                  </td>
                  <td className="px-4 py-3">{formatCtc(d.info.ctc_lpa_min, d.info.ctc_lpa_max)}</td>
                  <td className="px-4 py-3">
                    <EligibilityBadge value={d.eligibility} />
                  </td>
                  <td className="px-4 py-3">
                    <MatchBadge score={d.match_score} />
                  </td>
                  <td className="px-4 py-3 capitalize">{d.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
