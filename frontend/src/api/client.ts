/**
 * Small fetch wrapper: adds the bearer token, parses errors into ApiError, and on a 401
 * tries one refresh-token rotation before giving up.
 */
import type { ZodType } from "zod";
import { errorSchema, tokenSchema, type Tokens } from "./schemas";

export const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

/**
 * Tokens live in memory and sessionStorage (cleared when the tab closes).
 * Trade-off: simpler than httpOnly cookies, but readable by injected scripts (see LEARNING.md).
 */
const STORAGE_KEY = "driveradar.tokens";
let tokens: Tokens | null = loadTokens();
const listeners = new Set<(t: Tokens | null) => void>();

function loadTokens(): Tokens | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? tokenSchema.parse(JSON.parse(raw)) : null;
  } catch {
    return null;
  }
}

export function getTokens(): Tokens | null {
  return tokens;
}

export function setTokens(next: Tokens | null): void {
  tokens = next;
  try {
    if (next) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage unavailable (private mode): keep tokens in memory only */
  }
  listeners.forEach((fn) => fn(next));
}

export function onTokensChange(fn: (t: Tokens | null) => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

async function toApiError(res: Response): Promise<ApiError> {
  try {
    const parsed = errorSchema.safeParse(await res.json());
    if (parsed.success) {
      return new ApiError(res.status, parsed.data.error.code, parsed.data.error.message);
    }
  } catch {
    /* not JSON */
  }
  return new ApiError(res.status, "HTTP_ERROR", `Request failed (${res.status})`);
}

let refreshing: Promise<boolean> | null = null;

async function refreshTokens(): Promise<boolean> {
  const current = tokens;
  if (!current) return false;
  refreshing ??= (async () => {
    try {
      const res = await fetch(`${API_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: current.refresh_token }),
      });
      if (!res.ok) {
        setTokens(null);
        return false;
      }
      setTokens(tokenSchema.parse(await res.json()));
      return true;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

export interface RequestOptions {
  method?: string;
  json?: unknown;
  form?: FormData;
  auth?: boolean;
}

export async function request<T>(
  path: string,
  schema: ZodType<T> | null,
  opts: RequestOptions = {},
  retried = false,
): Promise<T> {
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  } else if (opts.form) {
    body = opts.form;
  }
  if (opts.auth !== false && tokens) headers.Authorization = `Bearer ${tokens.access_token}`;

  const res = await fetch(`${API_URL}${path}`, { method: opts.method ?? "GET", headers, body });
  if (res.status === 401 && opts.auth !== false && !retried && (await refreshTokens())) {
    return request(path, schema, opts, true);
  }
  if (!res.ok) throw await toApiError(res);
  if (res.status === 204 || schema === null) return undefined as T;
  return schema.parse(await res.json());
}
