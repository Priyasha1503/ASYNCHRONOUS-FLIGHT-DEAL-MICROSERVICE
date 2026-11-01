"use client";

import {
  ArrowLeft,
  CheckCircle2,
  CircleAlert,
  FlaskConical,
  Loader2,
  Pause,
  Play,
  RefreshCw,
  Trash2,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { MonitorStatusBadge, TargetProgress } from "@/components/monitoring/monitor-bits";
import { PriceHistoryChart } from "@/components/monitoring/price-history-chart";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, Skeleton } from "@/components/ui/card";
import { Input } from "@/components/ui/field";
import { FormAlert } from "@/components/ui/form-alert";
import { ApiError } from "@/lib/api";
import { useRequireUser } from "@/lib/auth";
import { formatMoney, localDate, relativeTime } from "@/lib/format";
import {
  FREQUENCIES,
  useCheckNow,
  useDeleteMonitor,
  useMonitor,
  useSimulatePriceChange,
  useUpdateMonitor,
  type MonitorDetail,
  type RefreshRun,
} from "@/lib/monitoring";
import { cn } from "@/lib/utils";

export default function MonitorPage() {
  const { id } = useParams<{ id: string }>();
  useRequireUser();
  // After a manual check/simulation we're "checking" until a run newer than the one that existed at
  // click time shows up (derived, no effect needed); a timer bounds the fast polling to 45 s.
  const [waitingAfter, setWaitingAfter] = useState<string | null | undefined>(undefined);
  const [latestSeen, setLatestSeen] = useState<string | null>(null);
  const q = useMonitor(id, { fast: waitingAfter !== undefined && latestSeen === waitingAfter });
  const latest = q.data?.runs[0]?.id ?? null;
  if (latest !== latestSeen) setLatestSeen(latest); // adjust state during render (React docs pattern)
  const checking = waitingAfter !== undefined && latest === waitingAfter;

  if (q.isPending) {
    return (
      <div className="mx-auto grid max-w-5xl gap-4 px-4 py-10 sm:px-6">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-28 rounded-xl" />
        <Skeleton className="h-80 rounded-xl" />
      </div>
    );
  }
  if (q.isError) {
    const notFound = q.error instanceof ApiError && q.error.status === 404;
    return (
      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
        <FormAlert
          message={
            notFound ? "This monitor doesn't exist or isn't yours." : "Couldn't load this monitor."
          }
        />
        <Button asChild variant="secondary" className="mt-4">
          <Link href="/monitors">Back to monitoring</Link>
        </Button>
      </div>
    );
  }
  const m = q.data;
  const waitForRun = () => {
    setWaitingAfter(m.runs[0]?.id ?? null);
    setTimeout(() => setWaitingAfter(undefined), 45_000);
  };

  return (
    <div className="mx-auto grid max-w-5xl gap-6 px-4 py-8 sm:px-6 sm:py-10">
      <Link
        href="/monitors"
        className="inline-flex w-fit items-center gap-1 text-sm text-muted hover:text-text"
      >
        <ArrowLeft className="size-4" aria-hidden /> All monitors
      </Link>
      <Header m={m} onQueued={waitForRun} checking={checking} />
      <Stats m={m} />
      <Card>
        <CardContent className="pt-5 sm:pt-6">
          <PriceHistoryChart history={m.history} currency={m.currency} target={m.target_price} />
        </CardContent>
      </Card>
      <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
        <Runs runs={m.runs} checking={checking} />
        <div className="grid content-start gap-6">
          <AlertSettings key={`${m.target_price}-${m.frequency_minutes}`} m={m} />
          {m.demo_simulation_available && <DemoSimulator id={m.id} onQueued={waitForRun} />}
        </div>
      </div>
    </div>
  );
}

function Header({
  m,
  onQueued,
  checking,
}: {
  m: MonitorDetail;
  onQueued: () => void;
  checking: boolean;
}) {
  const router = useRouter();
  const update = useUpdateMonitor(m.id);
  const check = useCheckNow(m.id);
  const del = useDeleteMonitor();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const searchHref = `/search?${new URLSearchParams({
    o: m.origin,
    d: m.destination,
    dep: m.depart_date,
    ...(m.return_date ? { ret: m.return_date } : {}),
  }).toString()}`;

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="font-display text-3xl font-semibold tracking-tight">{m.name}</h1>
          <MonitorStatusBadge status={m.status} />
        </div>
        <p className="mt-1 text-muted">
          {m.origin} → {m.destination} · {localDate(m.depart_date)}
          {m.return_date && ` – ${localDate(m.return_date)}`} ·{" "}
          <Link className="text-primary hover:underline" href={searchHref}>
            see current results
          </Link>
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          loading={check.isPending || checking}
          disabled={m.status !== "active"}
          onClick={() =>
            check.mutate(undefined, {
              onSuccess: (r) => {
                toast(r.message);
                onQueued();
              },
              onError: (e) =>
                toast.error(e instanceof ApiError ? e.message : "Couldn't queue a check"),
            })
          }
        >
          <RefreshCw aria-hidden /> {checking ? "Checking…" : "Check now"}
        </Button>
        {m.status !== "departed" && (
          <Button
            variant="secondary"
            loading={update.isPending}
            onClick={() =>
              update.mutate(
                { is_active: m.status !== "active" },
                {
                  onSuccess: (r) =>
                    toast(r.status === "active" ? "Monitoring resumed" : "Monitoring paused"),
                  onError: (e) =>
                    toast.error(e instanceof ApiError ? e.message : "Couldn't update"),
                },
              )
            }
          >
            {m.status === "active" ? <Pause aria-hidden /> : <Play aria-hidden />}
            {m.status === "active" ? "Pause" : "Resume"}
          </Button>
        )}
        {confirmDelete ? (
          <Button
            variant="danger"
            loading={del.isPending}
            onClick={() =>
              del.mutate(m.id, {
                onSuccess: () => {
                  toast("Monitor deleted");
                  router.push("/monitors");
                },
              })
            }
          >
            <Trash2 aria-hidden /> Confirm delete
          </Button>
        ) : (
          <Button variant="ghost" className="text-danger" onClick={() => setConfirmDelete(true)}>
            <Trash2 aria-hidden /> Delete
          </Button>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-subtle">{sub}</p>}
    </div>
  );
}

function Stats({ m }: { m: MonitorDetail }) {
  const nothing = m.last_checked_at !== null && m.last_price === null;
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <div className="rounded-xl border border-border bg-surface p-4 sm:col-span-2 lg:col-span-1">
        <p className="text-sm text-muted">Lowest now</p>
        <p className="mt-1 text-2xl font-semibold">
          {m.last_price ? formatMoney(m.last_price, m.currency) : nothing ? "None qualify" : "—"}
        </p>
        <div className="mt-2">
          <TargetProgress m={m} />
        </div>
      </div>
      <Stat
        label="Your target"
        value={m.target_price ? formatMoney(m.target_price, m.currency) : "Not set"}
        sub={
          m.drop_threshold_pct
            ? `Also alerts on drops ≥ ${Number(m.drop_threshold_pct)}%`
            : undefined
        }
      />
      <Stat
        label="Best seen"
        value={m.best_price ? formatMoney(m.best_price, m.currency) : "—"}
        sub={m.best_price_at ? relativeTime(m.best_price_at) : "From SkyScout's own checks"}
      />
      <Stat
        label="Last check"
        value={m.last_checked_at ? relativeTime(m.last_checked_at) : "Pending"}
        sub={
          m.next_check_at
            ? `Next: ${new Date(m.next_check_at) <= new Date() ? "due now" : new Date(m.next_check_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}`
            : m.status === "paused"
              ? "Paused"
              : undefined
        }
      />
    </div>
  );
}

const RUN_ICON: Record<
  RefreshRun["status"],
  { icon: typeof CheckCircle2; tone: string; label: string }
> = {
  succeeded: { icon: CheckCircle2, tone: "text-success", label: "Succeeded" },
  partial: { icon: CircleAlert, tone: "text-warning", label: "Partial" },
  failed: { icon: XCircle, tone: "text-danger", label: "Failed" },
  running: { icon: Loader2, tone: "text-info", label: "Running" },
};

function Runs({ runs, checking }: { runs: RefreshRun[]; checking: boolean }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent checks</CardTitle>
      </CardHeader>
      <CardContent>
        {runs.length === 0 && !checking ? (
          <p className="text-sm text-muted">
            No checks yet — the first one runs within about a minute.
          </p>
        ) : (
          <ol className="grid gap-0">
            {checking && (
              <li className="flex items-center gap-3 border-b border-border py-2.5 text-sm text-muted">
                <Loader2 className="size-4 animate-spin" aria-hidden /> Check in progress…
              </li>
            )}
            {runs.map((r) => {
              const s = RUN_ICON[r.status];
              const Icon = s.icon;
              return (
                <li
                  key={r.id}
                  className="flex items-start gap-3 border-b border-border py-2.5 last:border-0"
                >
                  <Icon
                    className={cn(
                      "mt-0.5 size-4 shrink-0",
                      s.tone,
                      r.status === "running" && "animate-spin",
                    )}
                    aria-hidden
                  />
                  <div className="min-w-0 flex-1 text-sm">
                    <p>
                      <span className="font-medium">{s.label}</span>
                      <span className="text-muted">
                        {" "}
                        · {r.trigger === "manual" ? "manual" : "scheduled"} ·{" "}
                        {relativeTime(r.started_at)}
                      </span>
                    </p>
                    <p className="text-xs text-muted">
                      {r.offers_count !== null && `${r.offers_count} offers · `}
                      {r.providers?.map((p) => `${p.provider}: ${p.state}`).join(", ")}
                      {r.error && r.status === "failed" && ` · ${r.error}`}
                    </p>
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}

function AlertSettings({ m }: { m: MonitorDetail }) {
  const update = useUpdateMonitor(m.id);
  const [target, setTarget] = useState(m.target_price ?? "");
  const [freq, setFreq] = useState(m.frequency_minutes);
  const valid = target === "" || /^\d+(\.\d{1,2})?$/.test(target.trim());
  const dirty = target !== (m.target_price ?? "") || freq !== m.frequency_minutes;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Alert settings</CardTitle>
      </CardHeader>
      <CardContent>
        <form
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (!valid) return;
            update.mutate(
              { target_price: target.trim() || null, frequency_minutes: freq },
              {
                onSuccess: () => toast.success("Alert settings saved"),
                onError: (err) =>
                  toast.error(err instanceof ApiError ? err.message : "Couldn't save"),
              },
            );
          }}
        >
          <label className="grid gap-1.5 text-sm font-medium">
            Target price ({m.currency})
            <Input
              inputMode="decimal"
              placeholder="Not set"
              value={target}
              aria-invalid={!valid || undefined}
              onChange={(e) => setTarget(e.target.value)}
            />
          </label>
          <label className="grid gap-1.5 text-sm font-medium">
            Check frequency
            <select
              value={freq}
              onChange={(e) => setFreq(Number(e.target.value))}
              className="h-10 rounded-md border border-border-strong bg-surface px-3 text-sm font-normal shadow-sm"
            >
              {FREQUENCIES.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </select>
            {m.effective_interval_minutes !== m.frequency_minutes && (
              <span className="text-xs font-normal text-muted">
                Shared schedule runs every {m.effective_interval_minutes} min (another traveller
                watches this route more often).
              </span>
            )}
          </label>
          <Button type="submit" disabled={!dirty || !valid} loading={update.isPending}>
            Save
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function DemoSimulator({ id, onQueued }: { id: string; onQueued: () => void }) {
  const sim = useSimulatePriceChange(id);
  return (
    <section
      aria-labelledby="demo-sim"
      className="rounded-xl border border-dashed border-accent/50 bg-accent-soft/50 p-5"
    >
      <h2 id="demo-sim" className="flex items-center gap-2 font-semibold">
        <FlaskConical className="size-4 text-accent-text" aria-hidden /> Simulate a price change
      </h2>
      <p className="mt-1 text-sm text-muted">
        Demo tool: shifts this trip&apos;s <em>demo</em> fares and runs a check, so you can see
        alerts fire. Not available for real fares or in production.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {[-25, -10, 10].map((p) => (
          <Button
            key={p}
            variant="secondary"
            size="sm"
            disabled={sim.isPending}
            onClick={() =>
              sim.mutate(p, {
                onSuccess: (r) => {
                  toast(r.message);
                  onQueued();
                },
                onError: (e) =>
                  toast.error(e instanceof ApiError ? e.message : "Simulation failed"),
              })
            }
          >
            {p > 0 ? `+${p}%` : `${p}%`}
          </Button>
        ))}
      </div>
    </section>
  );
}
