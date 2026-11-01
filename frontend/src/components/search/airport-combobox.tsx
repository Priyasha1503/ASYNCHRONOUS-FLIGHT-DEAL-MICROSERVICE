"use client";

import { MapPin, PlaneLanding, PlaneTakeoff } from "lucide-react";
import { useId, useMemo, useRef, useState } from "react";

import { useAirports, type Airport } from "@/lib/search";
import { cn } from "@/lib/utils";

type Props = {
  id: string;
  label: string;
  value: string;
  onChange: (iata: string) => void;
  onBlur?: () => void;
  error?: string;
  kind: "origin" | "destination";
  tone?: "light" | "dark";
};

function matches(a: Airport, q: string): number {
  const s = q.trim().toLowerCase();
  if (!s) return 0;
  if (a.iata.toLowerCase() === s) return 100;
  if (a.iata.toLowerCase().startsWith(s)) return 80;
  if (a.city.toLowerCase().startsWith(s)) return 60;
  if (a.name.toLowerCase().startsWith(s)) return 40;
  if (`${a.city} ${a.name}`.toLowerCase().includes(s)) return 20;
  return 0;
}

/** WAI-ARIA combobox (list autocomplete): type a city, airport or code; arrows + Enter to pick. */
export function AirportCombobox({ id, label, value, onChange, onBlur, error, kind, tone }: Props) {
  const { data: airports = [], isError } = useAirports();
  const byCode = useMemo(() => new Map(airports.map((a) => [a.iata, a])), [airports]);
  const selected = byCode.get(value);
  const [query, setQuery] = useState<string | null>(null); // null = not editing
  const [active, setActive] = useState(0);
  const listId = useId();
  const inputRef = useRef<HTMLInputElement>(null);

  const editing = query !== null;
  const options = useMemo(() => {
    if (!editing) return [];
    return airports
      .map((a) => [a, matches(a, query)] as const)
      .filter(([, s]) => s > 0 || !query.trim())
      .sort((x, y) => y[1] - x[1] || x[0].city.localeCompare(y[0].city))
      .slice(0, 8)
      .map(([a]) => a);
  }, [airports, editing, query]);

  const commit = (a: Airport) => {
    onChange(a.iata);
    setQuery(null);
  };

  const display = editing ? query : selected ? `${selected.city} (${selected.iata})` : value;
  const Icon = kind === "origin" ? PlaneTakeoff : PlaneLanding;
  const dark = tone === "dark";

  return (
    <div className="relative grid content-start gap-1.5">
      <label htmlFor={id} className={cn("text-sm font-medium", dark && "text-white/90")}>
        {label}
      </label>
      <div className="relative">
        <Icon
          className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-subtle"
          aria-hidden
        />
        <input
          ref={inputRef}
          id={id}
          role="combobox"
          aria-expanded={editing && options.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={editing && options[active] ? `${listId}-${active}` : undefined}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          autoComplete="off"
          placeholder={kind === "origin" ? "From — city or airport" : "To — city or airport"}
          value={display}
          onFocus={(e) => {
            setQuery("");
            setActive(0);
            requestAnimationFrame(() => e.target.select());
          }}
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
          }}
          onKeyDown={(e) => {
            if (!editing) return;
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setActive((i) => Math.min(i + 1, options.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((i) => Math.max(i - 1, 0));
            } else if (e.key === "Enter" && options[active]) {
              e.preventDefault();
              commit(options[active]);
            } else if (e.key === "Escape") {
              setQuery(null);
            } else if (e.key === "Tab" && options[active] && query.trim()) {
              commit(options[active]);
            }
          }}
          onBlur={() => {
            // Accept an exact code typed without picking from the list.
            const typed = query?.trim().toUpperCase();
            if (typed && byCode.has(typed)) onChange(typed);
            setQuery(null);
            onBlur?.();
          }}
          className={cn(
            "h-11 w-full rounded-md border bg-surface pr-3 pl-9 text-sm text-text shadow-sm outline-none",
            "transition-[border-color,box-shadow] duration-[var(--dur-fast)]",
            "focus-visible:border-primary focus-visible:ring-3 focus-visible:ring-primary/20 focus-visible:outline-none",
            error ? "border-danger" : "border-border-strong",
          )}
        />
        {editing && options.length > 0 && (
          <ul
            id={listId}
            role="listbox"
            aria-label={`${label} suggestions`}
            className="absolute z-30 mt-1 max-h-80 w-full min-w-64 overflow-auto rounded-lg border border-border bg-surface p-1 text-text shadow-lg"
          >
            {options.map((a, i) => (
              <li
                key={a.iata}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                // mousedown (not click) so it fires before the input's blur
                onMouseDown={(e) => {
                  e.preventDefault();
                  commit(a);
                }}
                onMouseEnter={() => setActive(i)}
                className={cn(
                  "flex cursor-pointer items-center gap-3 rounded-md px-2.5 py-2",
                  i === active && "bg-primary-soft",
                )}
              >
                <MapPin className="size-4 shrink-0 text-subtle" aria-hidden />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{a.city}</span>
                  <span className="block truncate text-xs text-muted">
                    {a.name} · {a.country}
                  </span>
                </span>
                <span className="font-mono text-xs font-semibold text-muted">{a.iata}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      {error ? (
        <p id={`${id}-error`} className={cn("text-sm", dark ? "text-[#ffb3c0]" : "text-danger")}>
          {error}
        </p>
      ) : isError ? (
        <p className={cn("text-sm", dark ? "text-white/75" : "text-muted")}>
          Airport list unavailable — type a 3-letter code.
        </p>
      ) : null}
    </div>
  );
}
