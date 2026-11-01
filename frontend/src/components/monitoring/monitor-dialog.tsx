"use client";

import { BellRing, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Field, Input, Label, Switch } from "@/components/ui/field";
import { FormAlert } from "@/components/ui/form-alert";
import { ApiError } from "@/lib/api";
import { formatMoney, localDate } from "@/lib/format";
import { FREQUENCIES, useCreateMonitor } from "@/lib/monitoring";
import { toRequestBody, type Offer, type SearchValues } from "@/lib/search";

const MONEY_RE = /^\d+(\.\d{1,2})?$/;

export function MonitorDialog({
  values,
  cheapest,
  onClose,
}: {
  values: SearchValues;
  cheapest: Offer | null;
  onClose: () => void;
}) {
  const router = useRouter();
  const create = useCreateMonitor();
  const uid = useId();
  const firstField = useRef<HTMLInputElement>(null);
  const suggested = cheapest ? String(Math.floor(Number(cheapest.total_amount) * 0.9)) : "";
  const [name, setName] = useState(
    `${values.origin} → ${values.destination}, ${localDate(values.depart)}`,
  );
  const [target, setTarget] = useState(suggested);
  const [dropPct, setDropPct] = useState("10");
  const [notifyNew, setNotifyNew] = useState(true);
  const [frequency, setFrequency] = useState(360);
  const [error, setError] = useState<string | null>(null);
  const [existing, setExisting] = useState<string | null>(null);

  useEffect(() => {
    firstField.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const targetError = target && !MONEY_RE.test(target.trim()) ? "Enter an amount, e.g. 450" : null;
  const dropNum = Number(dropPct);
  const dropError =
    dropPct && (!/^\d+(\.\d)?$/.test(dropPct) || dropNum <= 0 || dropNum > 90)
      ? "Between 1 and 90"
      : null;
  const nothingToWatch = !target && !dropPct && !notifyNew;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (targetError || dropError || nothingToWatch) return;
    try {
      const m = await create.mutateAsync({
        search: toRequestBody(values),
        name: name.trim() || undefined,
        target_price: target.trim() || null,
        drop_threshold_pct: dropPct || null,
        notify_new_qualifying: notifyNew,
        frequency_minutes: frequency,
      });
      toast.success("Monitoring started", {
        description: "The first check runs within about a minute.",
        action: { label: "View", onClick: () => router.push(`/monitors/${m.id}`) },
      });
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.push(`/signin?next=${encodeURIComponent(location.pathname + location.search)}`);
        return;
      }
      if (err instanceof ApiError && err.status === 409) {
        const d = err.details as { rule_id?: string } | undefined;
        if (d?.rule_id) setExisting(d.rule_id);
      }
      setError(err instanceof ApiError ? err.message : "Couldn't start monitoring.");
    }
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-end sm:place-items-center">
      <button
        aria-label="Close"
        className="absolute inset-0 bg-night-950/50"
        onClick={onClose}
        tabIndex={-1}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${uid}-title`}
        className="relative max-h-[92dvh] w-full overflow-auto rounded-t-2xl bg-surface p-6 shadow-lg sm:max-w-lg sm:rounded-2xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-full bg-primary-soft text-primary">
              <BellRing className="size-5" aria-hidden />
            </span>
            <div>
              <h2 id={`${uid}-title`} className="text-lg font-semibold">
                Monitor this trip
              </h2>
              <p className="text-sm text-muted">
                SkyScout re-checks this search and alerts you when it matters.
              </p>
            </div>
          </div>
          <Button variant="ghost" size="icon" aria-label="Close" onClick={onClose}>
            <X aria-hidden />
          </Button>
        </div>

        <form noValidate onSubmit={submit} className="mt-6 grid gap-5">
          <FormAlert message={error} />
          {existing && (
            <p className="-mt-2 text-sm">
              <Link
                className="font-medium text-primary hover:underline"
                href={`/monitors/${existing}`}
              >
                Open the existing monitor
              </Link>
            </p>
          )}
          <Field id={`${uid}-name`} label="Name">
            {(a) => (
              <Input
                {...a}
                maxLength={120}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            )}
          </Field>

          <Field
            id={`${uid}-target`}
            label={`Target price (${values.currency}, total)`}
            hint={
              cheapest
                ? `Cheapest flight meeting your requirements right now: ${formatMoney(cheapest.total_amount, cheapest.currency)}`
                : "No flight meets your requirements right now — you can still set a target."
            }
            error={targetError ?? undefined}
          >
            {(a) => (
              <Input
                {...a}
                ref={firstField}
                inputMode="decimal"
                placeholder="Optional"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
              />
            )}
          </Field>

          <div className="grid gap-5 sm:grid-cols-2">
            <Field
              id={`${uid}-drop`}
              label="Alert on a drop of (%)"
              hint="Since the previous check. Empty = off."
              error={dropError ?? undefined}
            >
              {(a) => (
                <Input
                  {...a}
                  inputMode="decimal"
                  placeholder="Off"
                  value={dropPct}
                  onChange={(e) => setDropPct(e.target.value)}
                />
              )}
            </Field>
            <Field id={`${uid}-freq`} label="Check" hint="Shared with other travellers">
              {(a) => (
                <select
                  {...a}
                  value={frequency}
                  onChange={(e) => setFrequency(Number(e.target.value))}
                  className="h-10 w-full rounded-md border border-border-strong bg-surface px-3 text-sm shadow-sm"
                >
                  {FREQUENCIES.map((f) => (
                    <option key={f.value} value={f.value}>
                      {f.label}
                    </option>
                  ))}
                </select>
              )}
            </Field>
          </div>

          <div className="flex items-center justify-between gap-4 rounded-lg border border-border p-3">
            <div>
              <Label htmlFor={`${uid}-new`}>Tell me when flights start qualifying</Label>
              <p className="text-sm text-muted">
                After a check where nothing met your requirements.
              </p>
            </div>
            <Switch id={`${uid}-new`} checked={notifyNew} onCheckedChange={setNotifyNew} />
          </div>

          {nothingToWatch && (
            <p className="text-sm text-warning">
              Choose at least one alert so there&apos;s something to watch.
            </p>
          )}

          <p className="text-xs text-subtle">
            Alerts use your requirements from this search (budget, stops, bags, airlines, times).
            Each event alerts once. Prices are search results, not guaranteed checkout prices.
          </p>

          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" loading={create.isPending} disabled={nothingToWatch}>
              <BellRing aria-hidden /> Start monitoring
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
