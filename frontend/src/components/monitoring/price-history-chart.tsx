"use client";

import { Table2, TrendingDown } from "lucide-react";
import { useId, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Button } from "@/components/ui/button";
import { formatMoney, formatMoneyShort } from "@/lib/format";
import type { HistoryPoint } from "@/lib/monitoring";

type Point = { t: number; price: number | null; raw: HistoryPoint };

function fmtWhen(t: number): string {
  return new Date(t).toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Cheapest flight meeting the rule's requirements at each check. Only actual observations are
 * plotted; a check where nothing qualified is a gap in the line (never interpolated), and the
 * table view lists every check, so no value is hover-only.
 */
export function PriceHistoryChart({
  history,
  currency,
  target,
}: {
  history: HistoryPoint[];
  currency: string;
  target: string | null;
}) {
  const [asTable, setAsTable] = useState(false);
  const titleId = useId();
  const data: Point[] = useMemo(
    () =>
      history.map((h) => ({
        t: new Date(h.checked_at).getTime(),
        price: h.cheapest_amount === null ? null : Number(h.cheapest_amount),
        raw: h,
      })),
    [history],
  );
  const priced = data.filter((d) => d.price !== null) as (Point & { price: number })[];
  const last = priced.at(-1);
  const targetNum = target === null ? null : Number(target);

  if (history.length === 0) {
    return (
      <div className="grid place-items-center gap-2 rounded-lg border border-dashed border-border-strong p-10 text-center">
        <TrendingDown className="size-6 text-subtle" aria-hidden />
        <p className="font-medium">No checks yet</p>
        <p className="max-w-sm text-sm text-muted">
          The first check runs within about a minute of creating the monitor. History appears here
          as real observations accumulate — SkyScout never fills in prices it didn&apos;t see.
        </p>
      </div>
    );
  }

  const values = priced.map((p) => p.price).concat(targetNum !== null ? [targetNum] : []);
  const lo = values.length ? Math.min(...values) : 0;
  const hi = values.length ? Math.max(...values) : 1;
  const pad = Math.max((hi - lo) * 0.15, hi * 0.03, 1);
  const spanMs = data.length > 1 ? data[data.length - 1]!.t - data[0]!.t : 0;

  return (
    <figure aria-labelledby={titleId} className="grid gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <figcaption id={titleId}>
          <span className="font-semibold">Cheapest flight meeting your requirements</span>
          <span className="block text-sm text-muted">
            {history.length} check{history.length === 1 ? "" : "s"} · {currency} total · gaps mean
            nothing qualified
          </span>
        </figcaption>
        <Button
          variant="ghost"
          size="sm"
          aria-pressed={asTable}
          onClick={() => setAsTable((v) => !v)}
        >
          <Table2 aria-hidden /> {asTable ? "Show chart" : "Show as table"}
        </Button>
      </div>

      {asTable ? (
        <div className="max-h-80 overflow-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-surface-2 text-left text-xs text-muted">
              <tr>
                <th className="px-3 py-2 font-medium">Checked</th>
                <th className="px-3 py-2 text-right font-medium">Cheapest qualifying</th>
                <th className="px-3 py-2 text-right font-medium">Qualifying</th>
                <th className="px-3 py-2 font-medium">Source</th>
              </tr>
            </thead>
            <tbody>
              {[...data].reverse().map((d) => (
                <tr key={d.t} className="border-t border-border">
                  <td className="px-3 py-2 tabular">{fmtWhen(d.t)}</td>
                  <td className="px-3 py-2 text-right tabular">
                    {d.price === null ? (
                      <span className="text-muted">None qualified</span>
                    ) : (
                      formatMoney(String(d.price), currency)
                    )}
                  </td>
                  <td className="px-3 py-2 text-right tabular">
                    {d.raw.qualifying} / {d.raw.total}
                  </td>
                  <td className="px-3 py-2 capitalize">{d.raw.source ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="h-64 w-full sm:h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 16, right: 56, bottom: 4, left: 4 }}>
              <CartesianGrid vertical={false} stroke="var(--chart-grid)" strokeWidth={1} />
              <XAxis
                dataKey="t"
                type="number"
                scale="time"
                domain={["dataMin", "dataMax"]}
                tickFormatter={(t: number) =>
                  // Short spans read better as times; longer ones as dates.
                  spanMs < 48 * 3600_000
                    ? new Date(t).toLocaleTimeString(undefined, {
                        hour: "2-digit",
                        minute: "2-digit",
                      })
                    : new Date(t).toLocaleDateString(undefined, { day: "numeric", month: "short" })
                }
                tick={{ fill: "var(--text-muted)", fontSize: 12 }}
                axisLine={{ stroke: "var(--border)" }}
                tickLine={false}
                minTickGap={40}
                padding={{ left: 12, right: 12 }}
              />
              <YAxis
                domain={[Math.max(0, lo - pad), hi + pad]}
                tickFormatter={(v: number) => formatMoneyShort(String(v), currency)}
                tick={{ fill: "var(--text-muted)", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                width={64}
                tickCount={5}
              />
              {targetNum !== null && (
                <ReferenceLine
                  y={targetNum}
                  stroke="var(--chart-2)"
                  strokeWidth={1.5}
                  strokeDasharray="5 4"
                  label={{
                    value: `Target ${formatMoneyShort(String(targetNum), currency)}`,
                    position: "insideTopRight",
                    fill: "var(--text-muted)",
                    fontSize: 12,
                  }}
                />
              )}
              <Tooltip
                content={(p) => (
                  <ChartTooltip active={p.active} payload={p.payload} currency={currency} />
                )}
                cursor={{ stroke: "var(--border-strong)", strokeWidth: 1 }}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="price"
                connectNulls={false}
                stroke="var(--chart-1)"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
                dot={{ r: 4, fill: "var(--chart-1)", stroke: "var(--surface)", strokeWidth: 2 }}
                activeDot={{
                  r: 6,
                  fill: "var(--chart-1)",
                  stroke: "var(--surface)",
                  strokeWidth: 2,
                }}
                isAnimationActive={false}
              />
              {last && (
                // Direct-label only the latest observed value (selective labelling).
                <ReferenceDot
                  x={last.t}
                  y={last.price}
                  r={0}
                  label={{
                    value: formatMoneyShort(String(last.price), currency),
                    position: "right",
                    offset: 10,
                    fill: "var(--text)",
                    fontSize: 12,
                    fontWeight: 600,
                  }}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </figure>
  );
}

function ChartTooltip({
  active,
  payload,
  currency,
}: {
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: unknown }>;
  currency: string;
}) {
  const point = payload?.[0]?.payload as Point | undefined;
  if (!active || !point) return null;
  return (
    <div className="rounded-lg border border-border bg-surface px-3 py-2 text-sm shadow-md">
      <p className="text-xs text-muted">{fmtWhen(point.t)}</p>
      <p className="font-semibold tabular">
        {point.price === null ? "Nothing qualified" : formatMoney(String(point.price), currency)}
      </p>
      <p className="text-xs text-muted">
        {point.raw.qualifying} of {point.raw.total} flights met your requirements
        {point.raw.source ? ` · ${point.raw.source}` : ""}
      </p>
    </div>
  );
}
