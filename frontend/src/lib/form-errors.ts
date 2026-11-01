import type { FieldValues, Path, UseFormSetError } from "react-hook-form";

import { ApiError } from "@/lib/api";

/**
 * Maps a backend error onto form fields where possible; returns a message for the form-level
 * banner otherwise. Keeps server validation visible next to the field that caused it.
 */
export function applyServerErrors<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  fields: readonly Path<T>[],
): string | null {
  if (!(error instanceof ApiError)) return "Something went wrong. Please try again.";
  const issues = error.fieldIssues();
  let mapped = false;
  for (const f of fields) {
    const msg = issues[f as string];
    if (msg) {
      setError(f, { type: "server", message: msg });
      mapped = true;
    }
  }
  if (mapped) return null;
  if (error.status === 429) return "Too many attempts. Wait a minute and try again.";
  return error.message;
}

/** Only allow same-site relative redirects (prevents open redirects via ?next=). */
export function safeNext(next: string | null, fallback = "/account"): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) {
    return fallback;
  }
  return next;
}
