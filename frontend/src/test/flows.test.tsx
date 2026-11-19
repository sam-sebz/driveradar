/** Main user flows, rendered with the real router and query client against a fake API. */
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { setTokens } from "../api/client";
import { json, makeDrive, mockFetch, tokens } from "./fixtures";
import { renderApp } from "./renderApp";

describe("student flow", () => {
  it("logs in, sees the dashboard sorted by the API, opens a drive", async () => {
    const soon = makeDrive({ id: "d2", closes_within_24h: true, info: { ...makeDrive().info, company: "Soon Ltd" } });
    const calls = mockFetch({
      "POST /auth/login": () => json(tokens),
      "GET /drives": () => json({ drives: [soon, makeDrive()] }),
      "GET /drives/d1": () => json(makeDrive()),
    });
    const user = userEvent.setup();
    renderApp("/login");

    await user.type(screen.getByLabelText("Email"), "demo@driveradar.dev");
    await user.type(screen.getByLabelText("Password"), "Demo@1234");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    const [, firstRow, secondRow, ...rest] = await screen.findAllByRole("row");
    expect(rest).toHaveLength(0); // header + 2 drives
    if (!firstRow || !secondRow) throw new Error("expected two drive rows");
    expect(within(firstRow).getByText("Soon Ltd")).toBeInTheDocument();
    expect(within(firstRow).getByText("Closes in < 24h")).toBeInTheDocument();
    expect(within(secondRow).getByText("50% match")).toBeInTheDocument();

    const loginBody = JSON.parse(String(calls[0]?.init?.body));
    expect(loginBody).toEqual({ email: "demo@driveradar.dev", password: "Demo@1234" });

    await user.click(screen.getByText("Kaveri Analytics Pvt. Ltd."));
    expect(await screen.findByRole("list", { name: "eligibility checklist" })).toHaveTextContent(
      "Your CGPA 8.2 >= required 7",
    );
    expect(screen.getByRole("list", { name: "missing skills" })).toHaveTextContent("SQL");
    expect(screen.getByText("₹1,50,000")).toBeInTheDocument();
  });

  it("shows the API error message on a failed login", async () => {
    mockFetch({
      "POST /auth/login": () =>
        json({ error: { code: "UNAUTHORIZED", message: "Invalid email or password" } }, 401),
    });
    const user = userEvent.setup();
    renderApp("/login");
    await user.type(screen.getByLabelText("Email"), "x@example.com");
    await user.type(screen.getByLabelText("Password"), "nope");
    await user.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password");
  });

  it("uploads a file and lists the roles found", async () => {
    setTokens(tokens);
    const calls = mockFetch({
      "POST /drives/upload": () =>
        json({ drives: [makeDrive(), makeDrive({ id: "d3", eligibility: "not_eligible" })] }, 201),
    });
    const user = userEvent.setup();
    renderApp("/upload");

    const file = new File(["%PDF-1.4"], "notice.pdf", { type: "application/pdf" });
    await user.upload(screen.getByTestId("file-input"), file);
    await user.click(screen.getByRole("button", { name: "Analyse notice" }));

    expect(await screen.findByText("Found 2 roles")).toBeInTheDocument();
    expect(screen.getByText("Not eligible")).toBeInTheDocument();
    const body = calls[0]?.init?.body as FormData;
    expect((body.get("file") as File).name).toBe("notice.pdf");
  });

  it("rejects unsupported files before uploading", async () => {
    setTokens(tokens);
    const calls = mockFetch({});
    const user = userEvent.setup({ applyAccept: false });
    renderApp("/upload");
    await user.upload(screen.getByTestId("file-input"), new File(["x"], "virus.exe"));
    expect(screen.getByRole("alert")).toHaveTextContent("Only PDF, DOCX and XLSX");
    expect(calls).toHaveLength(0);
  });

  it("edits a wrong field and shows the recomputed eligibility", async () => {
    setTokens(tokens);
    let current = makeDrive(); // the fake server keeps state, like the real one
    const calls = mockFetch({
      "GET /drives/d1": () => json(current),
      "PATCH /drives/d1": (init) => {
        current = makeDrive({ info: JSON.parse(String(init?.body)), eligibility: "not_eligible" });
        return json(current);
      },
      "GET /drives": () => json({ drives: [] }),
    });
    const user = userEvent.setup();
    renderApp("/drives/d1");

    await user.click(await screen.findByRole("button", { name: "Edit if wrong" }));
    const cgpa = screen.getByLabelText("Min CGPA");
    await user.clear(cgpa);
    await user.type(cgpa, "9.5");
    await user.click(screen.getByRole("button", { name: "Save and recheck eligibility" }));

    await waitFor(() => expect(screen.getAllByText("Not eligible").length).toBeGreaterThan(0));
    const patch = calls.find((c) => c.method === "PATCH");
    const sent = JSON.parse(String(patch?.init?.body));
    expect(sent.min_cgpa).toBe(9.5);
    expect(sent.deadline).toBe("2026-11-28T23:59:00+05:30");
    expect(sent.required_skills).toEqual(["Java", "SQL"]);
  });

  it("saves the profile", async () => {
    setTokens(tokens);
    const profile = {
      id: "u1", email: "a@example.com", role: "student", name: "Asha", branch: "CSE",
      batch: 2026, cgpa: 8.2, pct_10: 91, pct_12: 88, backlogs: 0, skills: ["Java"],
    };
    const calls = mockFetch({
      "GET /me/profile": () => json(profile),
      "PUT /me/profile": (init) => json({ ...profile, ...JSON.parse(String(init?.body)) }),
    });
    const user = userEvent.setup();
    renderApp("/profile");
    const skills = await screen.findByLabelText("Skills (comma separated)");
    await user.clear(skills);
    await user.type(skills, "Java, SQL");
    await user.click(screen.getByRole("button", { name: "Save profile" }));
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    const put = JSON.parse(String(calls.find((c) => c.method === "PUT")?.init?.body));
    expect(put.skills).toEqual(["Java", "SQL"]);
    expect(put.cgpa).toBe(8.2);
  });
});

describe("coordinator flow", () => {
  it("is sent to analytics and sees aggregated numbers", async () => {
    setTokens({ ...tokens, role: "coordinator" });
    mockFetch({
      "GET /analytics/skills": () =>
        json({ total_drives: 4, top_skills: [{ skill: "Python", count: 2 }] }),
      "GET /analytics/summary": () =>
        json({
          total_drives: 4, total_companies: 2, median_ctc_lpa: 6.13, drives_with_ctc: 4,
          drives_with_bond: 4,
          drives_by_role_category: [{ role_category: "Data & AI", count: 1 }],
        }),
    });
    renderApp("/");
    expect(await screen.findByText("6.13 LPA")).toBeInTheDocument();
    expect(screen.getByText("Data & AI")).toBeInTheDocument();
    expect(screen.getByTestId("skills-chart")).toBeInTheDocument();
  });
});

it("redirects anonymous users to login", () => {
  renderApp("/");
  expect(screen.getByRole("button", { name: "Log in" })).toBeInTheDocument();
});
