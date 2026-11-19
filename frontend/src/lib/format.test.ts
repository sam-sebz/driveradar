import { describe, expect, it } from "vitest";
import {
  formatCtc,
  formatDeadline,
  formatInr,
  formatPercent,
  fromIstLocalInput,
  hoursLeft,
  splitList,
  toIstLocalInput,
} from "./format";

describe("format helpers", () => {
  it("formats CTC ranges and single values", () => {
    expect(formatCtc(6.5, 8)).toBe("6.5 - 8 LPA");
    expect(formatCtc(12, 12)).toBe("12 LPA");
    expect(formatCtc(null, 5)).toBe("5 LPA");
    expect(formatCtc(null, null)).toBe("Not stated");
  });

  it("uses Indian digit grouping for rupees", () => {
    expect(formatInr(150000)).toBe("₹1,50,000");
    expect(formatInr(null)).toBe("Not stated");
  });

  it("shows deadlines in IST", () => {
    expect(formatDeadline("2026-11-28T18:29:00Z")).toContain("28 Nov 2026");
    expect(formatDeadline("2026-11-28T18:29:00Z")).toMatch(/11:59\s?pm/i);
    expect(formatDeadline(null)).toBe("Not stated");
  });

  it("formats match percentage, with n/a when the notice lists no skills", () => {
    expect(formatPercent(0.6)).toBe("60%");
    expect(formatPercent(null)).toBe("n/a");
  });

  it("round-trips IST datetime-local values", () => {
    const local = toIstLocalInput("2026-11-28T23:59:00+05:30");
    expect(local).toBe("2026-11-28T23:59");
    expect(fromIstLocalInput(local)).toBe("2026-11-28T23:59:00+05:30");
    expect(fromIstLocalInput("")).toBeNull();
    expect(toIstLocalInput(null)).toBe("");
  });

  it("computes hours left and splits comma lists", () => {
    const now = new Date("2026-11-28T00:00:00Z");
    expect(hoursLeft("2026-11-28T12:00:00Z", now)).toBe(12);
    expect(hoursLeft(null, now)).toBeNull();
    expect(splitList(" Java, , SQL ")).toEqual(["Java", "SQL"]);
    expect(splitList(" ")).toBeNull();
  });
});
