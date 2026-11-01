"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { z } from "zod";

import { api } from "@/lib/api";

// ── API types (mirror backend/app/api/v1/schemas/search.py) ─────────────────

export type FareSource = "live" | "cached" | "observed" | "historical" | "demo";
export type CabinClass = "economy" | "premium_economy" | "business" | "first";
export type ProviderState =
  | "ok"
  | "cached"
  | "timeout"
  | "rate_limited"
  | "circuit_open"
  | "unavailable"
  | "invalid_response"
  | "unsupported"
  | "error";

export type Segment = {
  carrier_code: string;
  carrier_name: string;
  flight_number: string | null;
  operating_carrier_code: string | null;
  origin: string;
  destination: string;
  departure_at: string;
  arrival_at: string;
  duration_minutes: number;
  aircraft: string | null;
};

export type Slice = {
  origin: string;
  destination: string;
  departure_at: string;
  arrival_at: string;
  duration_minutes: number;
  stops: number;
  arrival_day_offset: number;
  detail: "full" | "summary";
  layovers: { airport: string; minutes: number }[];
  segments: Segment[];
};

export type ScoreComponent = { factor: string; weight: number; score: number; note: string };

export type Offer = {
  id: string;
  fingerprint: string;
  provider: string;
  source: FareSource;
  total_amount: string;
  currency: string;
  cabin: CabinClass;
  fare_brand: string | null;
  baggage: { checked_bags: number | null; cabin_bag: boolean | null };
  booking_url: string | null;
  fetched_at: string;
  expires_at: string | null;
  total_duration_minutes: number;
  max_stops: number;
  score: number;
  score_components: ScoreComponent[];
  slices: Slice[];
};

export type Pick = { kind: string; offer_id: string; reasons: string[] };

export type ProviderStatus = {
  provider: string;
  display_name: string;
  source: FareSource;
  bookable: boolean;
  booking: "checkout" | "redirect" | "none";
  state: ProviderState;
  offers: number;
  latency_ms: number | null;
  fetched_at: string | null;
  message: string | null;
};

export type SearchResponse = {
  search_key: string;
  trip_type: "one_way" | "round_trip";
  currency: string;
  is_demo: boolean;
  cache_available: boolean;
  generated_at: string;
  providers: ProviderStatus[];
  summary: {
    received: number;
    invalid: number;
    duplicates_removed: number;
    qualifying: number;
    eliminated: number;
  };
  constraints: {
    total: number;
    qualifying: number;
    failed_by: Record<string, number>;
    relaxations: {
      constraint: string;
      unlocks: number;
      needed_value: string | null;
      unlocks_at_needed: number;
    }[];
  };
  recommendations: { cheapest: Pick | null; best_match: Pick | null; alternatives: Pick[] };
  offers: Offer[];
};

export type Airport = {
  iata: string;
  name: string;
  city: string;
  country: string;
  tz: string;
  nearby: string[];
};

// ── Form model (single source for form, URL and request body) ──────────────

export const CABINS: { value: CabinClass; label: string }[] = [
  { value: "economy", label: "Economy" },
  { value: "premium_economy", label: "Premium economy" },
  { value: "business", label: "Business" },
  { value: "first", label: "First" },
];
export const CURRENCIES = ["USD", "EUR", "GBP", "INR", "AUD", "CAD", "SGD", "AED", "JPY", "CHF"];

export const TIME_WINDOWS = {
  any: null,
  morning: { start_hour: 5, end_hour: 12, label: "Morning (05–12)" },
  afternoon: { start_hour: 12, end_hour: 18, label: "Afternoon (12–18)" },
  evening: { start_hour: 18, end_hour: 24, label: "Evening (18–24)" },
} as const;
export type TimeWindowKey = keyof typeof TIME_WINDOWS;

const iata = z
  .string()
  .trim()
  .regex(/^[A-Za-z]{3}$/, "Choose an airport")
  .transform((v) => v.toUpperCase());
const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Choose a date");

export const searchSchema = z
  .object({
    tripType: z.enum(["one_way", "round_trip"]),
    origin: iata,
    destination: iata,
    depart: isoDate,
    ret: z.string().optional(),
    adults: z.number().int().min(1).max(9),
    children: z.number().int().min(0).max(8),
    infants: z.number().int().min(0).max(8),
    cabin: z.enum(["economy", "premium_economy", "business", "first"]),
    currency: z.string().length(3),
    maxPrice: z
      .string()
      .trim()
      .regex(/^(\d+(\.\d{1,2})?)?$/, "Enter an amount, e.g. 450")
      .optional(),
    maxStops: z.enum(["any", "0", "1", "2"]),
    bag: z.boolean(),
    maxHours: z
      .string()
      .trim()
      .regex(/^(\d{1,2})?$/, "Whole hours, e.g. 14")
      .optional(),
    departWindow: z.enum(["any", "morning", "afternoon", "evening"]),
    strictTimes: z.boolean(),
    excluded: z.array(z.string()),
    nearby: z.boolean(),
  })
  .superRefine((v, ctx) => {
    if (v.origin === v.destination)
      ctx.addIssue({
        code: "custom",
        path: ["destination"],
        message: "Choose a different airport",
      });
    const today = new Date().toISOString().slice(0, 10);
    if (v.depart < today)
      ctx.addIssue({ code: "custom", path: ["depart"], message: "Departure is in the past" });
    if (v.tripType === "round_trip") {
      if (!v.ret || !/^\d{4}-\d{2}-\d{2}$/.test(v.ret))
        ctx.addIssue({ code: "custom", path: ["ret"], message: "Choose a return date" });
      else if (v.ret < v.depart)
        ctx.addIssue({ code: "custom", path: ["ret"], message: "Return is before departure" });
    }
    if (v.infants > v.adults)
      ctx.addIssue({ code: "custom", path: ["infants"], message: "One infant per adult" });
    if (v.adults + v.children + v.infants > 9)
      ctx.addIssue({ code: "custom", path: ["adults"], message: "At most 9 passengers" });
    const hours = Number(v.maxHours || 0);
    if (v.maxHours && (hours < 1 || hours > 72))
      ctx.addIssue({ code: "custom", path: ["maxHours"], message: "Between 1 and 72 hours" });
  });

export type SearchFormInput = z.input<typeof searchSchema>;
export type SearchValues = z.output<typeof searchSchema>;

function isoDaysFromNow(days: number): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export function defaultSearch(currency = "USD", origin = ""): SearchFormInput {
  return {
    tripType: "round_trip",
    origin,
    destination: "",
    depart: isoDaysFromNow(30),
    ret: isoDaysFromNow(37),
    adults: 1,
    children: 0,
    infants: 0,
    cabin: "economy",
    currency,
    maxPrice: "",
    maxStops: "any",
    bag: false,
    maxHours: "",
    departWindow: "any",
    strictTimes: false,
    excluded: [],
    nearby: false,
  };
}

// URL ⇄ form. Short keys keep shareable links readable.
export function toParams(v: SearchValues, sort?: string): URLSearchParams {
  const p = new URLSearchParams({ o: v.origin, d: v.destination, dep: v.depart });
  if (v.tripType === "round_trip" && v.ret) p.set("ret", v.ret);
  if (v.adults !== 1) p.set("ad", String(v.adults));
  if (v.children) p.set("ch", String(v.children));
  if (v.infants) p.set("inf", String(v.infants));
  if (v.cabin !== "economy") p.set("cab", v.cabin);
  if (v.currency !== "USD") p.set("cur", v.currency);
  if (v.maxPrice) p.set("max", v.maxPrice);
  if (v.maxStops !== "any") p.set("stops", v.maxStops);
  if (v.bag) p.set("bag", "1");
  if (v.maxHours) p.set("hrs", v.maxHours);
  if (v.departWindow !== "any") p.set("dw", v.departWindow);
  if (v.strictTimes) p.set("strict", "1");
  if (v.excluded.length) p.set("x", v.excluded.join(","));
  if (v.nearby) p.set("near", "1");
  if (sort && sort !== "best") p.set("sort", sort);
  return p;
}

export function fromParams(p: URLSearchParams): SearchValues | null {
  const ret = p.get("ret") ?? "";
  const candidate: SearchFormInput = {
    tripType: ret ? "round_trip" : "one_way",
    origin: p.get("o") ?? "",
    destination: p.get("d") ?? "",
    depart: p.get("dep") ?? "",
    ret,
    adults: Number(p.get("ad") ?? 1),
    children: Number(p.get("ch") ?? 0),
    infants: Number(p.get("inf") ?? 0),
    cabin: (p.get("cab") as CabinClass) ?? "economy",
    currency: p.get("cur") ?? "USD",
    maxPrice: p.get("max") ?? "",
    maxStops: (p.get("stops") as SearchFormInput["maxStops"]) ?? "any",
    bag: p.get("bag") === "1",
    maxHours: p.get("hrs") ?? "",
    departWindow: (p.get("dw") as TimeWindowKey) ?? "any",
    strictTimes: p.get("strict") === "1",
    excluded: (p.get("x") ?? "").split(",").filter(Boolean),
    nearby: p.get("near") === "1",
  };
  const parsed = searchSchema.safeParse(candidate);
  return parsed.success ? parsed.data : null;
}

export function toRequestBody(v: SearchValues) {
  const window = TIME_WINDOWS[v.departWindow];
  return {
    origin: v.origin,
    destination: v.destination,
    depart_date: v.depart,
    return_date: v.tripType === "round_trip" ? v.ret : null,
    passengers: { adults: v.adults, children: v.children, infants: v.infants },
    cabin: v.cabin,
    currency: v.currency,
    include_nearby: v.nearby,
    preferences: {
      max_price: v.maxPrice || null,
      max_stops: v.maxStops === "any" ? null : Number(v.maxStops),
      require_checked_bag: v.bag,
      max_duration_minutes: v.maxHours ? Number(v.maxHours) * 60 : null,
      excluded_airlines: v.excluded,
      departure_window: window
        ? { start_hour: window.start_hour, end_hour: window.end_hour }
        : null,
      time_windows_strict: v.strictTimes && !!window,
    },
  };
}

// ── Queries ──────────────────────────────────────────────────────────────────

export function useAirports() {
  return useQuery({
    queryKey: ["airports"],
    queryFn: () => api<Airport[]>("/airports"),
    staleTime: Infinity,
    gcTime: Infinity,
  });
}

export function useSearch(values: SearchValues | null) {
  const body = values ? toRequestBody(values) : null;
  return useQuery({
    queryKey: ["search", body],
    queryFn: ({ signal }) => api<SearchResponse>("/searches", { method: "POST", body, signal }),
    enabled: !!body,
    // Keep showing the previous results while a filter change re-runs the search.
    placeholderData: keepPreviousData,
    staleTime: 60_000,
    retry: false,
  });
}
