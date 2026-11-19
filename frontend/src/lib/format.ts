/** Display helpers. All dates are shown in Indian Standard Time. */

const IST = "Asia/Kolkata";

export function formatDeadline(iso: string | null): string {
  if (!iso) return "Not stated";
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: IST,
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function formatCtc(min: number | null, max: number | null): string {
  if (min === null && max === null) return "Not stated";
  if (min !== null && max !== null && min !== max) return `${min} - ${max} LPA`;
  return `${min ?? max} LPA`;
}

/** Indian digit grouping: 150000 -> ₹1,50,000 */
export function formatInr(value: number | null): string {
  if (value === null) return "Not stated";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatPercent(score: number | null): string {
  return score === null ? "n/a" : `${Math.round(score * 100)}%`;
}

export function hoursLeft(iso: string | null, now: Date = new Date()): number | null {
  if (!iso) return null;
  return (new Date(iso).getTime() - now.getTime()) / 3_600_000;
}

/** ISO string -> value for <input type="datetime-local"> in IST. */
export function toIstLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(new Date(iso).getTime() + 330 * 60_000);
  return d.toISOString().slice(0, 16);
}

/** <input type="datetime-local"> value (IST) -> ISO string with +05:30. */
export function fromIstLocalInput(value: string): string | null {
  return value ? `${value}:00+05:30` : null;
}

export function splitList(value: string): string[] | null {
  const items = value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return items.length ? items : null;
}
