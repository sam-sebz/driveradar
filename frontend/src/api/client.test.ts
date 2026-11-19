import { describe, expect, it } from "vitest";
import { json, mockFetch, tokens } from "../test/fixtures";
import { ApiError, getTokens, request, setTokens } from "./client";
import { profileSchema } from "./schemas";

const profile = {
  id: "u1",
  email: "a@example.com",
  role: "student",
  name: null,
  branch: "CSE",
  batch: 2026,
  cgpa: 8,
  pct_10: null,
  pct_12: null,
  backlogs: 0,
  skills: [],
};

describe("api client", () => {
  it("sends the bearer token", async () => {
    setTokens(tokens);
    const calls = mockFetch({ "GET /me/profile": () => json(profile) });
    await request("/me/profile", profileSchema);
    expect((calls[0]?.init?.headers as Record<string, string>).Authorization).toBe(
      "Bearer access-1",
    );
  });

  it("refreshes once on 401 and retries", async () => {
    setTokens(tokens);
    let first = true;
    mockFetch({
      "GET /me/profile": () => {
        if (first) {
          first = false;
          return json({ error: { code: "UNAUTHORIZED", message: "expired" } }, 401);
        }
        return json(profile);
      },
      "POST /auth/refresh": () => json({ ...tokens, access_token: "access-2" }),
    });
    const p = await request("/me/profile", profileSchema);
    expect(p.email).toBe("a@example.com");
    expect(getTokens()?.access_token).toBe("access-2");
  });

  it("logs out when refresh fails", async () => {
    setTokens(tokens);
    mockFetch({
      "GET /me/profile": () => json({ error: { code: "UNAUTHORIZED", message: "x" } }, 401),
      "POST /auth/refresh": () => json({ error: { code: "UNAUTHORIZED", message: "x" } }, 401),
    });
    await expect(request("/me/profile", profileSchema)).rejects.toBeInstanceOf(ApiError);
    expect(getTokens()).toBeNull();
  });

  it("turns error bodies into ApiError with code and message", async () => {
    setTokens(null);
    mockFetch({
      "POST /drives/upload": () =>
        json({ error: { code: "UNSUPPORTED_FILE", message: "Only PDF" } }, 415),
    });
    const err = await request("/drives/upload", null, { method: "POST" }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 415, code: "UNSUPPORTED_FILE", message: "Only PDF" });
  });

  it("handles non-JSON errors and 204 responses", async () => {
    mockFetch({
      "GET /boom": () => new Response("<html>", { status: 502 }),
      "DELETE /drives/d1": () => new Response(null, { status: 204 }),
    });
    await expect(request("/boom", null)).rejects.toMatchObject({ status: 502, code: "HTTP_ERROR" });
    await expect(request("/drives/d1", null, { method: "DELETE" })).resolves.toBeUndefined();
  });
});
