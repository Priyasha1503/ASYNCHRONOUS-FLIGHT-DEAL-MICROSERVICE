/**
 * Typed fetch wrapper for the SkyScout API (same-origin via the Next.js rewrite).
 * Handles the double-submit CSRF token and the backend's error envelope.
 */

const CSRF_COOKIE = "skyscout_csrf";
const CSRF_HEADER = "X-CSRF-Token";
const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export type FieldIssue = { loc: (string | number)[]; msg: string; type: string };

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details?: unknown,
    readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** Validation issues keyed by the last path segment (e.g. "email"). */
  fieldIssues(): Record<string, string> {
    if (!Array.isArray(this.details)) return {};
    const out: Record<string, string> = {};
    for (const d of this.details as FieldIssue[]) {
      const key = d.loc?.[d.loc.length - 1];
      if (typeof key === "string" && !out[key]) out[key] = d.msg;
    }
    return out;
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.split("; ").find((c) => c.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

let csrfInFlight: Promise<string> | null = null;

async function csrfToken(): Promise<string> {
  const existing = readCookie(CSRF_COOKIE);
  if (existing) return existing;
  csrfInFlight ??= fetch("/api/v1/auth/csrf", { credentials: "same-origin" })
    .then((r) => r.json() as Promise<{ csrf_token: string }>)
    .then((b) => b.csrf_token)
    .finally(() => {
      csrfInFlight = null;
    });
  return csrfInFlight;
}

type RequestOptions = { method?: string; body?: unknown; signal?: AbortSignal };

export async function api<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const method = (opts.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = { Accept: "application/json" };
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (UNSAFE.has(method)) headers[CSRF_HEADER] = await csrfToken();

  let res: Response;
  try {
    res = await fetch(`/api/v1${path}`, {
      method,
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
      credentials: "same-origin",
      signal: opts.signal,
    });
  } catch {
    throw new ApiError(0, "network_error", "Can't reach SkyScout. Check your connection.");
  }

  if (res.status === 204) return undefined as T;
  const payload: unknown = await res.json().catch(() => null);
  if (!res.ok) {
    const err = (payload as { error?: Record<string, unknown> } | null)?.error;
    throw new ApiError(
      res.status,
      typeof err?.code === "string" ? err.code : "http_error",
      typeof err?.message === "string" ? err.message : `Request failed (${res.status})`,
      err?.details,
      typeof err?.request_id === "string" ? err.request_id : undefined,
    );
  }
  return payload as T;
}
