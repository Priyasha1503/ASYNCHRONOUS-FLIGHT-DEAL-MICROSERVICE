"use client";

import { Briefcase, ChevronDown, ExternalLink, Info, Luggage } from "lucide-react";
import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { SourceBadge } from "@/components/ui/source-badge";
import {
  formatDuration,
  formatMoney,
  formatMoneyShort,
  localDate,
  localTime,
  relativeTime,
} from "@/lib/format";
import type { Offer, Slice } from "@/lib/search";
import { cn } from "@/lib/utils";

const AIRLINE_TONES = [
  "bg-[var(--chart-1)]",
  "bg-[var(--chart-2)]",
  "bg-[var(--chart-3)]",
  "bg-[var(--chart-4)]",
  "bg-[var(--night-700)]",
];

function airlineTone(code: string): string {
  const h = [...code].reduce((a, c) => a + c.charCodeAt(0), 0);
  return AIRLINE_TONES[h % AIRLINE_TONES.length]!;
}

export function AirlineMark({ code, name }: { code: string; name: string }) {
  return (
    <span
      title={name}
      className={cn(
        "grid size-9 shrink-0 place-items-center rounded-lg font-mono text-xs font-semibold text-white",
        airlineTone(code),
      )}
    >
      {code}
    </span>
  );
}

function stopsLabel(s: Slice): string {
  if (s.stops === 0) return "Nonstop";
  const count = `${s.stops} stop${s.stops > 1 ? "s" : ""}`;
  if (s.detail === "summary") return `${count} · connection details not provided`;
  const where = s.layovers.map((l) => `${l.airport} ${formatDuration(l.minutes)}`).join(", ");
  return `${count} · ${where}`;
}

export type BookingMode = "checkout" | "redirect" | "none";

/** Where the user goes to buy. Redirects are affiliate links: disclosed and marked sponsored. */
function BookingAction({ offer, booking }: { offer: Offer; booking: BookingMode }) {
  if (!offer.booking_url || booking === "none") {
    return (
      <p className="max-w-40 text-right text-xs text-muted">
        {offer.source === "demo" ? "Demo fare — not bookable" : "No booking link from this source"}
      </p>
    );
  }
  const observed = offer.source === "observed";
  const host = new URL(offer.booking_url).hostname.replace(/^www\./, "");
  return (
    <div className="grid justify-items-end gap-1 text-right">
      <Button asChild size="sm">
        <a href={offer.booking_url} target="_blank" rel="sponsored noopener noreferrer">
          {observed ? "Check price & book" : "Book"} <ExternalLink aria-hidden />
        </a>
      </Button>
      <p className="max-w-48 text-[11px] leading-snug text-subtle">
        {observed
          ? `Opens ${host}. Price was seen recently and may have changed — confirm it there.`
          : `Opens ${host} to complete booking.`}{" "}
        SkyScout may earn a commission.
      </p>
    </div>
  );
}

function SliceRow({ slice, label }: { slice: Slice; label: string }) {
  const carriers = [...new Map(slice.segments.map((s) => [s.carrier_code, s.carrier_name]))];
  const [code, name] = carriers[0]!;
  return (
    <div className="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-1">
      <AirlineMark code={code} name={name} />
      <div className="min-w-0">
        <p className="sr-only">
          {label}: {slice.origin} to {slice.destination}, {localDate(slice.departure_at)}
        </p>
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5" aria-hidden>
          <span className="text-lg font-semibold tabular">
            {localTime(slice.departure_at)}
            <span className="mx-1.5 text-subtle">→</span>
            {localTime(slice.arrival_at)}
            {slice.arrival_day_offset !== 0 && (
              <sup
                className="ml-0.5 text-xs font-medium text-accent-text"
                title="Arrives on a different day"
              >
                {slice.arrival_day_offset > 0 ? "+" : ""}
                {slice.arrival_day_offset}
              </sup>
            )}
          </span>
          <span className="text-sm text-muted tabular">
            {slice.origin}–{slice.destination} · {localDate(slice.departure_at)}
          </span>
        </div>
        <p className="text-sm text-muted">
          <span className="font-medium text-text">{formatDuration(slice.duration_minutes)}</span> ·{" "}
          <span className={cn(slice.stops === 0 && "text-success")}>{stopsLabel(slice)}</span> ·{" "}
          {carriers.map(([, n]) => n).join(" + ")}
        </p>
      </div>
    </div>
  );
}

function BaggageLine({ offer }: { offer: Offer }) {
  const bags = offer.baggage.checked_bags;
  if (bags === null)
    return (
      <span
        className="inline-flex items-center gap-1 text-warning"
        title="The provider did not confirm baggage"
      >
        <Info className="size-3.5" aria-hidden /> Checked bag: unknown
      </span>
    );
  return bags > 0 ? (
    <span className="inline-flex items-center gap-1 text-success">
      <Luggage className="size-3.5" aria-hidden /> {bags} checked bag{bags > 1 ? "s" : ""} included
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-muted">
      <Briefcase className="size-3.5" aria-hidden /> Cabin bag only
    </span>
  );
}

export function OfferCard({
  offer,
  highlight,
  reasons,
  booking,
  className,
}: {
  offer: Offer;
  highlight?: { label: string; icon: React.ReactNode; tone: "primary" | "accent" };
  reasons?: string[];
  booking: BookingMode;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const detailsId = useId();
  const labels = offer.slices.length > 1 ? ["Outbound", "Return"] : ["Outbound"];

  return (
    <article
      aria-label={`${formatMoney(offer.total_amount, offer.currency)} ${offer.slices[0]!.origin} to ${offer.slices[0]!.destination}`}
      className={cn(
        "overflow-hidden rounded-xl border bg-surface transition-shadow duration-[var(--dur-base)] hover:shadow-md",
        highlight?.tone === "primary"
          ? "border-primary/50 shadow-md"
          : highlight?.tone === "accent"
            ? "border-accent/50 shadow-md"
            : "border-border shadow-sm",
        className,
      )}
    >
      {highlight && (
        <div
          className={cn(
            "flex items-center gap-2 px-5 py-2 text-sm font-semibold",
            highlight.tone === "primary"
              ? "bg-primary-soft text-primary"
              : "bg-accent-soft text-accent-text",
          )}
        >
          {highlight.icon}
          {highlight.label}
        </div>
      )}
      <div className="grid gap-5 p-5 md:grid-cols-[1fr_auto]">
        <div className="grid gap-4">
          {offer.slices.map((s, i) => (
            <SliceRow key={i} slice={s} label={labels[i]!} />
          ))}
          {reasons && reasons.length > 0 && (
            <ul className="grid gap-1 text-sm text-muted">
              {reasons.map((r) => (
                <li key={r} className="flex gap-2">
                  <span aria-hidden className="mt-2 size-1 shrink-0 rounded-full bg-primary" />
                  {r}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="flex flex-row items-end justify-between gap-3 border-t border-border pt-4 md:min-w-48 md:flex-col md:items-end md:border-t-0 md:border-l md:pt-0 md:pl-5">
          <div className="md:text-right">
            <p className="font-display text-3xl font-semibold tabular">
              {formatMoneyShort(offer.total_amount, offer.currency)}
            </p>
            <p className="text-xs text-muted">
              Total · {formatMoney(offer.total_amount, offer.currency)}
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5 md:justify-end">
              {/* An observed fare's age is unknown (seen within ~48 h); don't imply it's fresh. */}
              <SourceBadge
                source={offer.source}
                detail={
                  offer.source === "observed" ? "seen recently" : relativeTime(offer.fetched_at)
                }
              />
            </div>
          </div>
          <BookingAction offer={offer} booking={booking} />
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border bg-surface-2/60 px-5 py-2.5 text-sm">
        <BaggageLine offer={offer} />
        {offer.fare_brand && <span className="text-muted">{offer.fare_brand} fare</span>}
        <button
          type="button"
          aria-expanded={open}
          aria-controls={detailsId}
          onClick={() => setOpen((o) => !o)}
          className="ml-auto inline-flex items-center gap-1 rounded font-medium text-primary hover:underline"
        >
          {open ? "Hide details" : "Flight details"}
          <ChevronDown
            className={cn("size-4 transition-transform", open && "rotate-180")}
            aria-hidden
          />
        </button>
      </div>
      {open && <OfferDetails id={detailsId} offer={offer} labels={labels} />}
    </article>
  );
}

function OfferDetails({ id, offer, labels }: { id: string; offer: Offer; labels: string[] }) {
  return (
    <div id={id} className="grid gap-6 border-t border-border p-5 lg:grid-cols-[1.4fr_1fr]">
      <div className="grid gap-5">
        {offer.slices.map((s, i) => (
          <section key={i} aria-label={labels[i]}>
            <h3 className="text-sm font-semibold">
              {labels[i]} · {localDate(s.departure_at)}
            </h3>
            {s.detail === "summary" ? (
              <div className="mt-2 grid gap-1 text-sm">
                <p className="tabular">
                  {localTime(s.departure_at)} {s.origin} → {localTime(s.arrival_at)} {s.destination}{" "}
                  · {formatDuration(s.duration_minutes)}
                </p>
                <p className="text-xs text-muted">
                  {s.segments[0]!.carrier_code}
                  {s.segments[0]!.flight_number ? ` ${s.segments[0]!.flight_number}` : ""} ·{" "}
                  {s.stops === 0 ? "nonstop" : `${s.stops} stop${s.stops > 1 ? "s" : ""}`}. This
                  source doesn&apos;t list connection airports or every flight number — see them on
                  the booking site.
                </p>
              </div>
            ) : (
              <ol className="mt-3 grid gap-3 border-l-2 border-border pl-4">
                {s.segments.map((seg, j) => (
                  <li key={j} className="relative">
                    <span
                      aria-hidden
                      className="absolute top-1.5 -left-[1.3rem] size-2.5 rounded-full border-2 border-primary bg-surface"
                    />
                    <p className="text-sm font-medium tabular">
                      {localTime(seg.departure_at)} {seg.origin} → {localTime(seg.arrival_at)}{" "}
                      {seg.destination}
                    </p>
                    <p className="text-xs text-muted">
                      {seg.carrier_name} {seg.carrier_code}
                      {seg.flight_number} · {formatDuration(seg.duration_minutes)}
                      {seg.aircraft ? ` · ${seg.aircraft}` : ""}
                    </p>
                    {s.layovers[j] && (
                      <p className="mt-2 rounded-md bg-surface-2 px-2 py-1 text-xs text-muted">
                        Layover in {s.layovers[j]!.airport} ·{" "}
                        {formatDuration(s.layovers[j]!.minutes)}
                      </p>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </section>
        ))}
        <p className="text-xs text-subtle">
          Times are local to each airport.{" "}
          {offer.source === "observed"
            ? "This is a recently seen fare for one adult, not a live quote; the booking site shows the current price."
            : `Price is for all travellers, as returned by ${offer.provider}; the final price is confirmed by the provider at checkout.`}
        </p>
      </div>
      <section aria-label="Why this ranking">
        <h3 className="text-sm font-semibold">Why this ranking · {offer.score.toFixed(1)}/100</h3>
        <ul className="mt-3 grid gap-3">
          {offer.score_components.map((c) => (
            <li key={c.factor}>
              <div className="flex justify-between text-xs">
                <span className="font-medium capitalize">{c.factor}</span>
                <span className="text-muted tabular">weight {Math.round(c.weight * 100)}%</span>
              </div>
              <div
                className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-sunken"
                role="meter"
                aria-label={`${c.factor} score`}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Math.round(c.score * 100)}
              >
                <div
                  className="h-full rounded-full bg-primary"
                  style={{ width: `${c.score * 100}%` }}
                />
              </div>
              <p className="mt-1 text-xs text-muted">{c.note}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
