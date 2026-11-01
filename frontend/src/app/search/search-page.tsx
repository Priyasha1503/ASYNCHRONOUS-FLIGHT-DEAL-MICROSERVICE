"use client";

import { ArrowRight, BellRing, Pencil, X } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { MonitorDialog } from "@/components/monitoring/monitor-dialog";
import {
  ResultsError,
  ResultsSkeleton,
  ResultsView,
  SORTS,
  type SortKey,
} from "@/components/results/results-view";
import { summarizePassengers } from "@/components/search/passengers-picker";
import { SearchForm } from "@/components/search/search-form";
import { Button } from "@/components/ui/button";
import { useMe } from "@/lib/auth";
import { localDate } from "@/lib/format";
import { CABINS, defaultSearch, fromParams, useSearch, type SearchValues } from "@/lib/search";

export function SearchPage() {
  const params = useSearchParams();
  const values = fromParams(params);
  const sortParam = params.get("sort") ?? "best";
  const sort: SortKey = sortParam in SORTS ? (sortParam as SortKey) : "best";
  const { data: me } = useMe();
  const search = useSearch(values);
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [monitoring, setMonitoring] = useState(false);

  if (!values) {
    const prefill = defaultSearch(me?.preferences.currency, me?.preferences.home_airport ?? "");
    if (params.get("o")) prefill.origin = params.get("o")!;
    if (params.get("d")) prefill.destination = params.get("d")!;
    return (
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <h1 className="font-display text-3xl font-semibold tracking-tight">Search flights</h1>
        <p className="mt-2 text-muted">
          {params.toString()
            ? "Some search details were missing or out of date — check them below."
            : "Tell SkyScout where you're going and what matters to you."}
        </p>
        <SearchForm className="mt-6" defaultValues={prefill} showAdvanced />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
      <div className="mb-6">
        {editing ? (
          <div className="grid gap-2">
            <div className="flex justify-end">
              <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>
                <X aria-hidden /> Close
              </Button>
            </div>
            <SearchForm
              defaultValues={values}
              sort={sort}
              submitLabel="Update search"
              onSubmitted={() => setEditing(false)}
            />
          </div>
        ) : (
          <SearchSummary
            values={values}
            onEdit={() => setEditing(true)}
            onMonitor={() => {
              if (me) setMonitoring(true);
              else
                router.push(`/signin?next=${encodeURIComponent(`/search?${params.toString()}`)}`);
            }}
            canMonitor={!search.isPending && !search.isError}
          />
        )}
      </div>
      {monitoring && search.data && (
        <MonitorDialog
          values={values}
          cheapest={
            search.data.offers.find(
              (o) => o.id === search.data.recommendations.cheapest?.offer_id,
            ) ?? null
          }
          onClose={() => setMonitoring(false)}
        />
      )}

      {search.isPending ? (
        <div aria-live="polite">
          <p className="sr-only">Searching flights…</p>
          <SearchProgress />
          <ResultsSkeleton />
        </div>
      ) : search.isError ? (
        <ResultsError error={search.error} onRetry={() => void search.refetch()} />
      ) : (
        <ResultsView
          data={search.data}
          values={values}
          sort={sort}
          refreshing={search.isPlaceholderData || search.isFetching}
        />
      )}
    </div>
  );
}

function SearchSummary({
  values,
  onEdit,
  onMonitor,
  canMonitor,
}: {
  values: SearchValues;
  onEdit: () => void;
  onMonitor: () => void;
  canMonitor: boolean;
}) {
  const cabin = CABINS.find((c) => c.value === values.cabin)?.label ?? values.cabin;
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface px-5 py-4 shadow-sm sm:flex-row sm:items-center">
      <div className="min-w-0 flex-1">
        <h1 className="flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          {values.origin}
          <ArrowRight className="size-5 text-subtle" aria-label="to" />
          {values.destination}
          {values.tripType === "round_trip" && (
            <span className="text-base font-normal text-muted">round trip</span>
          )}
        </h1>
        <p className="mt-0.5 text-sm text-muted">
          {localDate(values.depart)}
          {values.tripType === "round_trip" && values.ret && ` – ${localDate(values.ret)}`} ·{" "}
          {summarizePassengers(values)} · {cabin} · {values.currency}
          {values.nearby && " · nearby airports"}
        </p>
      </div>
      <div className="flex flex-wrap gap-2 self-start sm:self-auto">
        <Button variant="secondary" onClick={onEdit}>
          <Pencil aria-hidden /> Edit search
        </Button>
        <Button onClick={onMonitor} disabled={!canMonitor}>
          <BellRing aria-hidden /> Monitor this trip
        </Button>
      </div>
    </div>
  );
}

/** Brief, honest progress indicator: animates only while the request is actually in flight. */
function SearchProgress() {
  return (
    <div
      className="mb-6 overflow-hidden rounded-full bg-surface-sunken"
      role="progressbar"
      aria-label="Searching"
    >
      <div className="search-progress h-1 w-1/3 rounded-full bg-gradient-to-r from-[var(--violet-500)] via-[var(--magenta-500)] to-[var(--coral-400)]" />
    </div>
  );
}
