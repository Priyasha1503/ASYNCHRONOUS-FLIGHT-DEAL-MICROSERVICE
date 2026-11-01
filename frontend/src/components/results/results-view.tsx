"use client";

import {
  AlertTriangle,
  Award,
  CircleDollarSign,
  FlaskConical,
  RefreshCw,
  SearchX,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useId, useMemo, useOptimistic, useState, useTransition } from "react";

import { OfferCard } from "@/components/results/offer-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/card";
import { Label, Switch } from "@/components/ui/field";
import { ApiError } from "@/lib/api";
import { formatDuration, formatMoneyShort, plural, relativeTime } from "@/lib/format";
import {
  TIME_WINDOWS,
  toParams,
  type Offer,
  type ProviderState,
  type SearchResponse,
  type SearchValues,
} from "@/lib/search";
import { cn } from "@/lib/utils";

export const SORTS = {
  best: { label: "Best match", key: (o: Offer) => -o.score },
  cheapest: { label: "Cheapest", key: (o: Offer) => Number(o.total_amount) },
  fastest: { label: "Fastest", key: (o: Offer) => o.total_duration_minutes },
  earliest: {
    label: "Earliest departure",
    key: (o: Offer) => new Date(o.slices[0]!.departure_at).getTime(),
  },
} as const;
export type SortKey = keyof typeof SORTS;

const CONSTRAINT_LABEL: Record<string, string> = {
  budget: "Over your budget",
  max_stops: "More stops than allowed",
  checked_bag: "No checked bag included",
  bag_unconfirmed: "Checked bag not confirmed",
  max_duration: "Longer than your max journey time",
  excluded_airline: "Uses an airline you excluded",
  departure_window: "Outside your departure window",
  arrival_window: "Outside your arrival window",
};

const STATE_LABEL: Record<ProviderState, string> = {
  ok: "Responded",
  cached: "From shared cache",
  timeout: "Timed out",
  rate_limited: "Rate limited",
  circuit_open: "Paused after errors",
  unavailable: "Unavailable",
  invalid_response: "Sent invalid data",
  unsupported: "Doesn't cover this search",
  error: "Error",
};

/**
 * The URL is the source of truth for filters and sort. Controls render from an *optimistic* copy so
 * they respond instantly; it settles to the URL once the navigation transition completes.
 */
function useUpdateSearch(values: SearchValues, sort: SortKey) {
  const router = useRouter();
  const pathname = usePathname();
  const [view, setView] = useOptimistic({ values, sort });
  const [, startTransition] = useTransition();
  const update = (patch: Partial<SearchValues>, nextSort: SortKey = view.sort) => {
    const next = { values: { ...view.values, ...patch }, sort: nextSort };
    startTransition(() => {
      setView(next);
      router.replace(`${pathname}?${toParams(next.values, next.sort).toString()}`, {
        scroll: false,
      });
    });
  };
  return { view, update };
}

// ── Overview ─────────────────────────────────────────────────────────────────

function Overview({ data }: { data: SearchResponse }) {
  const failing = data.providers.filter((p) => p.state !== "ok" && p.state !== "cached");
  return (
    <div className="grid gap-3">
      {data.is_demo && (
        <div
          role="note"
          className="flex items-start gap-3 rounded-lg border border-accent/40 bg-accent-soft px-4 py-3 text-sm"
        >
          <FlaskConical className="mt-0.5 size-4 shrink-0 text-accent-text" aria-hidden />
          <p>
            <span className="font-semibold text-accent-text">Demo data.</span> These fares come from
            SkyScout&apos;s built-in demo provider: fictional airlines and synthetic prices, useful
            for trying the product. They are not real offers and can&apos;t be booked.
          </p>
        </div>
      )}
      {failing.length > 0 && (
        <div
          role="status"
          className="flex items-start gap-3 rounded-lg border border-warning/40 bg-warning-soft px-4 py-3 text-sm"
        >
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
          <p>
            Results may be incomplete:{" "}
            {failing
              .map((p) => `${p.display_name} — ${STATE_LABEL[p.state].toLowerCase()}`)
              .join("; ")}
            .
          </p>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-muted">
        <span>
          <span className="font-semibold text-text">{data.summary.qualifying}</span> of{" "}
          {data.constraints.total} flights meet your requirements
        </span>
        <span aria-hidden className="hidden h-4 w-px bg-border sm:block" />
        <span className="flex flex-wrap items-center gap-2">
          {data.providers.map((p) => (
            <span
              key={p.provider}
              title={p.message ?? undefined}
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 py-0.5 text-xs"
            >
              <span
                aria-hidden
                className={cn(
                  "size-1.5 rounded-full",
                  p.state === "ok" || p.state === "cached" ? "bg-success" : "bg-warning",
                )}
              />
              {p.display_name}: {STATE_LABEL[p.state]}
              {p.fetched_at && ` · ${relativeTime(p.fetched_at)}`}
            </span>
          ))}
        </span>
      </div>
    </div>
  );
}

// ── Filters (hard constraints → re-run search, served from cache) ─────────────

function Filters({
  values,
  data,
  update,
  className,
}: {
  values: SearchValues;
  data: SearchResponse;
  update: (p: Partial<SearchValues>) => void;
  className?: string;
}) {
  const airlines = useMemo(() => {
    const m = new Map<string, string>();
    for (const o of data.offers)
      for (const s of o.slices) for (const g of s.segments) m.set(g.carrier_code, g.carrier_name);
    for (const code of values.excluded) if (!m.has(code)) m.set(code, code);
    return [...m].sort((a, b) => a[1].localeCompare(b[1]));
  }, [data.offers, values.excluded]);
  // Two instances can be mounted at once (sidebar + mobile sheet): ids and radio-group names must
  // be unique per instance, or the browser merges the radio groups and labels hit the wrong input.
  const uid = useId();

  return (
    <div className={cn("grid content-start gap-6", className)}>
      <fieldset className="grid gap-2">
        <legend className="mb-1 text-sm font-semibold">Stops</legend>
        {(
          [
            ["any", "Any"],
            ["0", "Nonstop only"],
            ["1", "Up to 1 stop"],
            ["2", "Up to 2 stops"],
          ] as const
        ).map(([v, label]) => (
          <label key={v} className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name={`${uid}-stops`}
              checked={values.maxStops === v}
              onChange={() => update({ maxStops: v })}
              className="accent-[var(--primary)]"
            />
            {label}
          </label>
        ))}
      </fieldset>

      {/* Keyed so the draft resets when the budget changes elsewhere (e.g. a relax button). */}
      <BudgetFilter key={values.maxPrice ?? ""} values={values} update={update} />

      <fieldset className="grid gap-2">
        <legend className="mb-1 text-sm font-semibold">Departure time</legend>
        <select
          aria-label="Departure time"
          value={values.departWindow}
          onChange={(e) => update({ departWindow: e.target.value as SearchValues["departWindow"] })}
          className="h-10 rounded-md border border-border-strong bg-surface px-2 text-sm"
        >
          <option value="any">Any time</option>
          {(["morning", "afternoon", "evening"] as const).map((k) => (
            <option key={k} value={k}>
              {TIME_WINDOWS[k].label}
            </option>
          ))}
        </select>
        {values.departWindow !== "any" && (
          <div className="flex items-center justify-between gap-2">
            <Label htmlFor={`${uid}-strict`} className="font-normal">
              Only this window
            </Label>
            <Switch
              id={`${uid}-strict`}
              checked={values.strictTimes}
              onCheckedChange={(v) => update({ strictTimes: v })}
            />
          </div>
        )}
      </fieldset>

      <div className="flex items-center justify-between gap-2">
        <Label htmlFor={`${uid}-bag`}>Checked bag required</Label>
        <Switch
          id={`${uid}-bag`}
          checked={values.bag}
          onCheckedChange={(v) => update({ bag: v })}
        />
      </div>

      {airlines.length > 0 && (
        <fieldset className="grid gap-2">
          <legend className="mb-1 text-sm font-semibold">Airlines</legend>
          {airlines.map(([code, name]) => (
            <label key={code} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={!values.excluded.includes(code)}
                onChange={(e) =>
                  update({
                    excluded: e.target.checked
                      ? values.excluded.filter((c) => c !== code)
                      : [...values.excluded, code],
                  })
                }
                className="accent-[var(--primary)]"
              />
              {name}
            </label>
          ))}
        </fieldset>
      )}
    </div>
  );
}

function BudgetFilter({
  values,
  update,
}: {
  values: SearchValues;
  update: (p: Partial<SearchValues>) => void;
}) {
  const [draft, setDraft] = useState(values.maxPrice ?? "");
  const valid = /^(\d+(\.\d{1,2})?)?$/.test(draft.trim());
  const inputId = `${useId()}-budget`;
  return (
    <form
      className="grid gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) update({ maxPrice: draft.trim() });
      }}
    >
      <label htmlFor={inputId} className="text-sm font-semibold">
        Budget ({values.currency}, total)
      </label>
      <div className="flex gap-2">
        <input
          id={inputId}
          inputMode="decimal"
          placeholder="No limit"
          value={draft}
          aria-invalid={!valid || undefined}
          onChange={(e) => setDraft(e.target.value)}
          className="h-10 w-full rounded-md border border-border-strong bg-surface px-3 text-sm aria-invalid:border-danger"
        />
        <Button type="submit" variant="secondary" disabled={!valid}>
          Apply
        </Button>
      </div>
    </form>
  );
}

// ── Main view ────────────────────────────────────────────────────────────────

export function ResultsView({
  data,
  values: urlValues,
  sort: urlSort,
  refreshing,
}: {
  data: SearchResponse;
  values: SearchValues;
  sort: SortKey;
  refreshing: boolean;
}) {
  const {
    view: { values, sort },
    update,
  } = useUpdateSearch(urlValues, urlSort);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const byId = useMemo(() => new Map(data.offers.map((o) => [o.id, o])), [data.offers]);
  const sorted = useMemo(
    () =>
      [...data.offers].sort(
        (a, b) => SORTS[sort].key(a) - SORTS[sort].key(b) || a.id.localeCompare(b.id),
      ),
    [data.offers, sort],
  );
  const booking = new Map(data.providers.map((p) => [p.provider, p.booking]));
  const { cheapest, best_match, alternatives } = data.recommendations;
  const same = cheapest && best_match && cheapest.offer_id === best_match.offer_id;

  return (
    <div
      className={cn("grid gap-6 transition-opacity", refreshing && "opacity-60")}
      aria-busy={refreshing}
    >
      <Overview data={data} />

      <div className="grid gap-8 lg:grid-cols-[15rem_1fr]">
        {/* Filters: sidebar on desktop, sheet on mobile */}
        <aside aria-label="Filters" className="hidden lg:block">
          <div className="sticky top-24 rounded-xl border border-border bg-surface p-5">
            <h2 className="mb-4 font-semibold">Filters</h2>
            <Filters values={values} data={data} update={update} />
          </div>
        </aside>
        {filtersOpen && (
          <div
            className="fixed inset-0 z-50 lg:hidden"
            role="dialog"
            aria-modal="true"
            aria-label="Filters"
          >
            <button
              aria-label="Close filters"
              className="absolute inset-0 bg-night-950/50"
              onClick={() => setFiltersOpen(false)}
            />
            <div className="absolute inset-x-0 bottom-0 max-h-[85dvh] overflow-auto rounded-t-2xl bg-surface p-5 shadow-lg">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="font-semibold">Filters</h2>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Close"
                  onClick={() => setFiltersOpen(false)}
                >
                  <X aria-hidden />
                </Button>
              </div>
              <Filters values={values} data={data} update={update} />
              <Button className="mt-6 w-full" onClick={() => setFiltersOpen(false)}>
                Show {plural(data.summary.qualifying, "flight")}
              </Button>
            </div>
          </div>
        )}

        <div className="grid min-w-0 content-start gap-8">
          <div className="flex items-center justify-between gap-3 lg:hidden">
            <Button variant="secondary" onClick={() => setFiltersOpen(true)}>
              <SlidersHorizontal aria-hidden /> Filters
            </Button>
          </div>

          {data.offers.length === 0 ? (
            <NoResults data={data} values={values} update={update} />
          ) : (
            <>
              <section aria-labelledby="recs-title" className="grid gap-4">
                <h2 id="recs-title" className="font-display text-2xl font-semibold tracking-tight">
                  Recommended for you
                </h2>
                {cheapest && byId.get(cheapest.offer_id) && (
                  <OfferCard
                    offer={byId.get(cheapest.offer_id)!}
                    booking={booking.get(byId.get(cheapest.offer_id)!.provider) ?? "none"}
                    reasons={cheapest.reasons}
                    highlight={{
                      label: same
                        ? "Cheapest qualifying · Best overall match"
                        : "Cheapest qualifying flight",
                      icon: <CircleDollarSign className="size-4" aria-hidden />,
                      tone: "accent",
                    }}
                  />
                )}
                {!same && best_match && byId.get(best_match.offer_id) && (
                  <OfferCard
                    offer={byId.get(best_match.offer_id)!}
                    booking={booking.get(byId.get(best_match.offer_id)!.provider) ?? "none"}
                    reasons={best_match.reasons}
                    highlight={{
                      label: "Best overall match",
                      icon: <Award className="size-4" aria-hidden />,
                      tone: "primary",
                    }}
                  />
                )}
                {alternatives.length > 0 && (
                  <div className="grid gap-3">
                    <h3 className="text-sm font-semibold text-muted">Worth considering</h3>
                    {alternatives.map((alt) => {
                      const o = byId.get(alt.offer_id);
                      return o ? (
                        <OfferCard
                          key={alt.offer_id}
                          offer={o}
                          booking={booking.get(o.provider) ?? "none"}
                          reasons={alt.reasons}
                        />
                      ) : null;
                    })}
                  </div>
                )}
              </section>

              <section aria-labelledby="all-title" className="grid gap-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h2 id="all-title" className="font-display text-2xl font-semibold tracking-tight">
                    All {plural(data.offers.length, "flight")}
                  </h2>
                  <label className="flex items-center gap-2 text-sm">
                    <span className="text-muted">Sort by</span>
                    <select
                      value={sort}
                      onChange={(e) => update({}, e.target.value as SortKey)}
                      className="h-9 rounded-md border border-border-strong bg-surface px-2 text-sm"
                    >
                      {Object.entries(SORTS).map(([k, s]) => (
                        <option key={k} value={k}>
                          {s.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                {sorted.map((o) => (
                  <OfferCard key={o.id} offer={o} booking={booking.get(o.provider) ?? "none"} />
                ))}
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function NoResults({
  data,
  values,
  update,
}: {
  data: SearchResponse;
  values: SearchValues;
  update: (p: Partial<SearchValues>) => void;
}) {
  const noData = data.constraints.total === 0;
  // Each button states exactly how many flights *that* change adds: the smallest relaxation adds
  // `unlocks_at_needed`; removing the limit entirely (offered separately) adds `unlocks`.
  const actions = data.constraints.relaxations.flatMap((r) => {
    const out: { label: string; patch: Partial<SearchValues>; unlocks: number }[] = [];
    const step = relaxAction(r.constraint, r.needed_value, values);
    if (step) out.push({ ...step, unlocks: r.unlocks_at_needed });
    const remove = REMOVE_LIMIT[r.constraint];
    if (remove && r.unlocks > r.unlocks_at_needed) out.push({ ...remove, unlocks: r.unlocks });
    return out;
  });
  return (
    <section className="grid justify-items-start gap-4 rounded-xl border border-border bg-surface p-6 sm:p-8">
      <span className="grid size-12 place-items-center rounded-full bg-surface-2 text-muted">
        <SearchX className="size-6" aria-hidden />
      </span>
      {noData ? (
        <>
          <h2 className="font-display text-2xl font-semibold">No flights found for this search</h2>
          <p className="max-w-prose text-muted">
            None of the connected providers returned flights for this route and date. Try nearby
            airports or different dates.
          </p>
        </>
      ) : (
        <>
          <h2 className="font-display text-2xl font-semibold">
            None of the {data.constraints.total} flights meet all your requirements
          </h2>
          <p className="max-w-prose text-muted">
            SkyScout never quietly ignores your limits. Here&apos;s what ruled flights out:
          </p>
          <ul className="grid gap-1 text-sm">
            {Object.entries(data.constraints.failed_by).map(([c, n]) => (
              <li key={c}>
                <span className="font-medium">{CONSTRAINT_LABEL[c] ?? c}</span>{" "}
                <span className="text-muted">— {plural(n, "flight")}</span>
              </li>
            ))}
          </ul>
          {actions.length > 0 && (
            <div className="grid gap-2">
              <p className="text-sm font-semibold">Relax one requirement:</p>
              <div className="flex flex-wrap gap-2">
                {actions.map((a) => (
                  <Button
                    key={a.label}
                    variant="secondary"
                    onClick={() => update(a.patch)}
                    className="h-auto min-h-10 py-2 text-left whitespace-normal"
                  >
                    {a.label} <span className="text-muted">(+{plural(a.unlocks, "flight")})</span>
                  </Button>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}

const REMOVE_LIMIT: Record<string, { label: string; patch: Partial<SearchValues> }> = {
  budget: { label: "Remove budget limit", patch: { maxPrice: "" } },
  max_stops: { label: "Allow any number of stops", patch: { maxStops: "any" } },
  max_duration: { label: "Remove journey-time limit", patch: { maxHours: "" } },
};

function relaxAction(
  constraint: string,
  needed: string | null,
  v: SearchValues,
): { label: string; patch: Partial<SearchValues> } | null {
  switch (constraint) {
    case "budget":
      return needed
        ? {
            label: `Raise budget to ${formatMoneyShort(String(Math.ceil(Number(needed))), v.currency)}`,
            patch: { maxPrice: String(Math.ceil(Number(needed))) },
          }
        : null;
    case "max_stops":
      return needed
        ? {
            label: `Allow ${needed} stop${needed === "1" ? "" : "s"}`,
            patch: { maxStops: needed as SearchValues["maxStops"] },
          }
        : null;
    case "max_duration":
      return needed
        ? {
            label: `Allow up to ${formatDuration(Math.ceil(Number(needed) / 60) * 60)}`,
            patch: { maxHours: String(Math.ceil(Number(needed) / 60)) },
          }
        : null;
    case "checked_bag":
    case "bag_unconfirmed":
      return { label: "Don't require a checked bag", patch: { bag: false } };
    case "excluded_airline":
      return { label: "Include all airlines", patch: { excluded: [] } };
    case "departure_window":
    case "arrival_window":
      return { label: "Treat time window as a preference", patch: { strictTimes: false } };
    default:
      return null;
  }
}

export function ResultsSkeleton() {
  return (
    <div className="grid gap-6" aria-hidden>
      <Skeleton className="h-12 w-full" />
      <div className="grid gap-8 lg:grid-cols-[15rem_1fr]">
        <Skeleton className="hidden h-96 lg:block" />
        <div className="grid content-start gap-4">
          <Skeleton className="h-8 w-56" />
          {[0, 1, 2].map((i) => (
            <div key={i} className="rounded-xl border border-border bg-surface p-5">
              <div className="grid gap-5 md:grid-cols-[1fr_auto]">
                <div className="grid gap-4">
                  {[0, 1].map((j) => (
                    <div key={j} className="flex items-center gap-3">
                      <Skeleton className="size-9 rounded-lg" />
                      <div className="grid flex-1 gap-2">
                        <Skeleton className="h-5 w-48" />
                        <Skeleton className="h-4 w-64 max-w-full" />
                      </div>
                    </div>
                  ))}
                </div>
                <div className="grid justify-items-end gap-2">
                  <Skeleton className="h-8 w-24" />
                  <Skeleton className="h-4 w-20" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function ResultsError({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const msg =
    error instanceof ApiError
      ? error.status === 429
        ? "You're searching very quickly — wait a few seconds and try again."
        : error.status === 422
          ? error.message
          : error.status === 0
            ? error.message
            : "Search failed on our side. Please try again."
      : "Search failed. Please try again.";
  return (
    <div
      role="alert"
      className="grid justify-items-start gap-3 rounded-xl border border-danger/30 bg-danger-soft p-6"
    >
      <p className="font-semibold text-danger">We couldn&apos;t complete this search</p>
      <p className="text-sm">{msg}</p>
      {error instanceof ApiError && error.requestId && (
        <p className="text-xs text-muted">Reference: {error.requestId}</p>
      )}
      <Button variant="secondary" onClick={onRetry}>
        <RefreshCw aria-hidden /> Try again
      </Button>
    </div>
  );
}
