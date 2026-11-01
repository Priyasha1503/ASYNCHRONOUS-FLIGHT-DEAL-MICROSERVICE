/**
 * Display helpers. Flight times are shown in the *airport's* local time exactly as the API sends
 * them (ISO-8601 with the airport offset) — never converted to the viewer's timezone.
 */

export function formatMoney(amount: string, currency: string): string {
  const n = Number(amount);
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    maximumFractionDigits: currency === "JPY" ? 0 : 2,
  }).format(n);
}

/** Whole-unit price for headlines (e.g. "$412"); exact value stays available in details. */
export function formatMoneyShort(amount: string, currency: string): string {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Math.round(Number(amount)));
}

export function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (!h) return `${m}m`;
  return m ? `${h}h ${String(m).padStart(2, "0")}m` : `${h}h`;
}

/** "09:05" from "2026-12-10T09:05:00+01:00" — airport-local wall time. */
export function localTime(iso: string): string {
  return iso.slice(11, 16);
}

/** "Thu 10 Dec" from an ISO date or datetime, without timezone conversion. */
export function localDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number) as [number, number, number];
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
}

export function relativeTime(iso: string, now: number = Date.now()): string {
  const diffS = Math.round((now - new Date(iso).getTime()) / 1000);
  if (diffS < 45) return "just now";
  const mins = Math.round(diffS / 60);
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs} h ago`;
  return `${Math.round(hrs / 24)} d ago`;
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}
