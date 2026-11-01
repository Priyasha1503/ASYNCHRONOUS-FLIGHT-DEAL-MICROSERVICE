"use client";

import { Minus, Plus, Users } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { cn } from "@/lib/utils";

type Counts = { adults: number; children: number; infants: number };

const ROWS: { key: keyof Counts; label: string; hint: string; min: number }[] = [
  { key: "adults", label: "Adults", hint: "12+ years", min: 1 },
  { key: "children", label: "Children", hint: "2–11 years", min: 0 },
  { key: "infants", label: "Infants", hint: "Under 2, on lap", min: 0 },
];

export function summarizePassengers({ adults, children, infants }: Counts): string {
  const parts = [`${adults} adult${adults > 1 ? "s" : ""}`];
  if (children) parts.push(`${children} child${children > 1 ? "ren" : ""}`);
  if (infants) parts.push(`${infants} infant${infants > 1 ? "s" : ""}`);
  return parts.join(", ");
}

export function PassengersPicker({
  value,
  onChange,
  error,
  tone,
}: {
  value: Counts;
  onChange: (v: Counts) => void;
  error?: string;
  tone?: "light" | "dark";
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const panelId = useId();
  const total = value.adults + value.children + value.infants;

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const canInc = (k: keyof Counts) =>
    total < 9 && (k !== "infants" || value.infants < value.adults);
  const canDec = (k: keyof Counts, min: number) =>
    value[k] > min && !(k === "adults" && value.infants >= value.adults);

  return (
    <div ref={ref} className="relative grid content-start gap-1.5">
      <span className={cn("text-sm font-medium", tone === "dark" && "text-white/90")}>
        Passengers
      </span>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "flex h-11 w-full items-center gap-2 rounded-md border bg-surface px-3 text-left text-sm text-text shadow-sm",
          error ? "border-danger" : "border-border-strong",
        )}
      >
        <Users className="size-4 text-subtle" aria-hidden />
        <span className="truncate">{summarizePassengers(value)}</span>
      </button>
      {open && (
        <div
          id={panelId}
          role="group"
          aria-label="Passengers"
          className="absolute top-full z-30 mt-1 w-72 rounded-lg border border-border bg-surface p-4 text-text shadow-lg"
        >
          {ROWS.map((r) => (
            <div key={r.key} className="flex items-center justify-between gap-3 py-2">
              <div>
                <p className="text-sm font-medium">{r.label}</p>
                <p className="text-xs text-muted">{r.hint}</p>
              </div>
              <div className="flex items-center gap-3">
                <Stepper
                  label={`Fewer ${r.label.toLowerCase()}`}
                  disabled={!canDec(r.key, r.min)}
                  onClick={() => onChange({ ...value, [r.key]: value[r.key] - 1 })}
                >
                  <Minus />
                </Stepper>
                <span className="w-5 text-center tabular" aria-live="polite">
                  {value[r.key]}
                </span>
                <Stepper
                  label={`More ${r.label.toLowerCase()}`}
                  disabled={!canInc(r.key)}
                  onClick={() => onChange({ ...value, [r.key]: value[r.key] + 1 })}
                >
                  <Plus />
                </Stepper>
              </div>
            </div>
          ))}
          <p className="mt-2 text-xs text-muted">Up to 9 travellers; one infant per adult.</p>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="mt-3 w-full rounded-md bg-primary py-2 text-sm font-medium text-primary-fg"
          >
            Done
          </button>
        </div>
      )}
      {error && <p className="text-sm text-danger">{error}</p>}
    </div>
  );
}

function Stepper({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="grid size-8 place-items-center rounded-full border border-border-strong text-text transition-colors hover:bg-surface-2 disabled:opacity-40 [&_svg]:size-3.5"
    >
      {children}
    </button>
  );
}
