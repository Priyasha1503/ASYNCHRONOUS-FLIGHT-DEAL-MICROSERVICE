"use client";

import { ArrowRight, BellRing, Search } from "lucide-react";
import Link from "next/link";

import { MonitorStatusBadge, TargetProgress } from "@/components/monitoring/monitor-bits";
import { Button } from "@/components/ui/button";
import { Card, Skeleton } from "@/components/ui/card";
import { FormAlert } from "@/components/ui/form-alert";
import { useRequireUser } from "@/lib/auth";
import { formatMoney, localDate, relativeTime } from "@/lib/format";
import { FREQUENCIES, useMonitors } from "@/lib/monitoring";

export default function MonitorsPage() {
  const me = useRequireUser();
  const monitors = useMonitors();

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-tight">Monitoring</h1>
          <p className="mt-2 text-muted">Trips SkyScout is watching for you.</p>
        </div>
        <Button asChild variant="secondary">
          <Link href="/search">
            <Search aria-hidden /> New search
          </Link>
        </Button>
      </div>

      <div className="mt-8 grid gap-4">
        {me.isPending || monitors.isPending ? (
          [0, 1].map((i) => <Skeleton key={i} className="h-36 rounded-xl" />)
        ) : monitors.isError ? (
          <FormAlert message="Couldn't load your monitors. Please try again." />
        ) : monitors.data.length === 0 ? (
          <Card className="grid justify-items-start gap-3 p-8">
            <span className="grid size-12 place-items-center rounded-full bg-primary-soft text-primary">
              <BellRing className="size-6" aria-hidden />
            </span>
            <h2 className="text-xl font-semibold">No trips monitored yet</h2>
            <p className="max-w-prose text-muted">
              Search for a trip, then choose <strong>Monitor this trip</strong> on the results page
              to set a target price. SkyScout re-checks it on a schedule and alerts you once per
              meaningful change.
            </p>
            <Button asChild className="mt-2">
              <Link href="/search">Search flights</Link>
            </Button>
          </Card>
        ) : (
          monitors.data.map((m) => (
            <Link
              key={m.id}
              href={`/monitors/${m.id}`}
              className="group rounded-xl border border-border bg-surface p-5 shadow-sm transition-shadow hover:shadow-md"
            >
              <div className="grid gap-4 sm:grid-cols-[1fr_16rem] sm:items-center">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="truncate text-lg font-semibold">{m.name}</h2>
                    <MonitorStatusBadge status={m.status} />
                  </div>
                  <p className="mt-1 text-sm text-muted">
                    {m.origin} → {m.destination} · {localDate(m.depart_date)}
                    {m.return_date && ` – ${localDate(m.return_date)}`} ·{" "}
                    {FREQUENCIES.find((f) => f.value === m.frequency_minutes)?.label ??
                      `${m.frequency_minutes} min`}
                  </p>
                  <p className="mt-1 text-xs text-subtle">
                    {m.last_checked_at
                      ? `Checked ${relativeTime(m.last_checked_at)}`
                      : "Not checked yet"}
                    {m.best_price && ` · best seen ${formatMoney(m.best_price, m.currency)}`}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex-1">
                    <TargetProgress m={m} />
                  </div>
                  <ArrowRight
                    className="size-4 text-subtle transition-transform group-hover:translate-x-0.5"
                    aria-hidden
                  />
                </div>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}
