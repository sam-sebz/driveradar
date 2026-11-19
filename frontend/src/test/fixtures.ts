import { vi } from "vitest";
import type { Drive } from "../api/schemas";

export const tokens = {
  access_token: "access-1",
  refresh_token: "refresh-1",
  token_type: "bearer",
  expires_in: 900,
  role: "student" as const,
};

export function makeDrive(overrides: Partial<Drive> = {}): Drive {
  return {
    id: "d1",
    info: {
      company: "Kaveri Analytics Pvt. Ltd.",
      role: "Associate Software Engineer",
      location: "Chennai",
      ctc_lpa_min: 6.5,
      ctc_lpa_max: 8,
      stipend_per_month: null,
      deadline: "2026-11-28T23:59:00+05:30",
      joining_date: "2027-07-01",
      bond_years: 2,
      bond_penalty_inr: 150000,
      min_cgpa: 7,
      min_ug_percent: null,
      min_percent_10th: 60,
      min_percent_12th: 60,
      max_active_backlogs: 0,
      eligible_branches: ["CSE", "IT"],
      eligible_batch: [2026],
      required_skills: ["Java", "SQL"],
      selection_process: ["Online Assessment"],
      notes: null,
    },
    role_category: "Software Engineering",
    source_filename: "notice.pdf",
    extraction_provider: "mock",
    created_at: "2026-11-19T10:00:00Z",
    eligibility: "eligible",
    eligibility_reasons: [
      { rule: "cgpa", status: "pass", reason: "Your CGPA 8.2 >= required 7" },
      { rule: "branch", status: "pass", reason: "Your branch CSE is eligible" },
    ],
    match_score: 0.5,
    matched_skills: ["Java"],
    missing_skills: ["SQL"],
    status: "saved",
    closes_within_24h: false,
    is_closed: false,
    ...overrides,
  };
}

type Handler = (init: RequestInit | undefined, url: URL) => Response | Promise<Response>;

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Install a fake fetch: keys are "METHOD /path". Unmatched calls fail the test. */
export function mockFetch(routes: Record<string, Handler>) {
  const calls: { method: string; path: string; init?: RequestInit }[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(typeof input === "string" ? input : input.toString());
    const method = init?.method ?? "GET";
    calls.push({ method, path: url.pathname + url.search, init });
    const handler = routes[`${method} ${url.pathname}${url.search}`] ?? routes[`${method} ${url.pathname}`];
    if (!handler) throw new Error(`Unexpected request ${method} ${url.pathname}${url.search}`);
    return handler(init, url);
  });
  vi.stubGlobal("fetch", fn);
  return calls;
}
