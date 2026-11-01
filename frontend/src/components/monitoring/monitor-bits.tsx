import { CheckCircle2, CircleDashed, PauseCircle, PlaneLanding } from "lucide-react";

import { formatMoney, formatMoneyShort } from "@/lib/format";
import type { Monitor, MonitorStatus } from "@/lib/monitoring";
import { cn } from "@/lib/utils";

const STATUS: Record<MonitorStatus, { label: string; icon: typeof CheckCircle2; tone: string }> = {
  active: { label: "Monitoring", icon: CircleDashed, tone: "bg-success-soft text-success" },
  paused: { label: "Paused", icon: PauseCircle, tone: "bg-surface-2 text-muted" },
  departed: { label: "Departure passed", icon: PlaneLanding, tone: "bg-surface-2 text-muted" },
};

/** Status is always icon + text, never colour alone. */
export function MonitorStatusBadge({ status }: { status: MonitorStatus }) {
  const s = STATUS[status];
  const Icon = s.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        s.tone,
      )}
    >
      <Icon className="size-3" aria-hidden />
      {s.label}
    </span>
  );
}

/** Current price relative to target: a meter plus an explicit sentence. */
export function TargetProgress({ m }: { m: Monitor }) {
  if (m.last_checked_at === null) {
    return <p className="text-sm text-muted">Waiting for the first check…</p>;
  }
  if (m.last_price === null) {
    return <p className="text-sm text-muted">No flight met your requirements at the last check.</p>;
  }
  const price = Number(m.last_price);
  if (m.target_price === null) {
    return (
      <p className="text-sm">
        Lowest now{" "}
        <span className="font-semibold tabular">{formatMoney(m.last_price, m.currency)}</span>
        <span className="text-muted"> · no target set</span>
      </p>
    );
  }
  const target = Number(m.target_price);
  const reached = price <= target;
  const best = m.best_price ? Number(m.best_price) : price;
  // Meter spans from the highest relevant price down to the target.
  const top = Math.max(price, best, target) * 1.05;
  const pct = reached ? 100 : Math.max(4, Math.min(96, ((top - price) / (top - target)) * 100));
  return (
    <div className="grid gap-1.5">
      <div
        className="h-1.5 overflow-hidden rounded-full bg-primary-soft"
        role="meter"
        aria-label="Progress toward target price"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct)}
      >
        <div
          className={cn("h-full rounded-full", reached ? "bg-success" : "bg-primary")}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-sm">
        {reached ? (
          <span className="inline-flex items-center gap-1 font-medium text-success">
            <CheckCircle2 className="size-3.5" aria-hidden /> At or below your target
          </span>
        ) : (
          <>
            <span className="font-semibold tabular">
              {formatMoneyShort(String(price - target), m.currency)}
            </span>{" "}
            <span className="text-muted">
              above your {formatMoneyShort(m.target_price, m.currency)} target
            </span>
          </>
        )}
      </p>
    </div>
  );
}
