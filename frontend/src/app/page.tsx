import {
  ArrowRight,
  BellRing,
  Filter,
  Layers,
  Scale,
  Search,
  ShieldCheck,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";

import { HeroSearch } from "@/app/hero-actions";
import { SkyBackdrop } from "@/components/site/sky-backdrop";
import { Button } from "@/components/ui/button";
import { SOURCE_DESCRIPTIONS, SourceBadge, type FareSource } from "@/components/ui/source-badge";

const PICKS: { title: string; body: string; icon: LucideIcon }[] = [
  {
    title: "Cheapest qualifying",
    body: "The lowest fare that satisfies every hard requirement — budget, stops, bags, times.",
    icon: Filter,
  },
  {
    title: "Best overall match",
    body: "The strongest balance of price, duration, stops and your preferences, with the reasons.",
    icon: Scale,
  },
  {
    title: "Worth a look",
    body: "Real trade-offs: a shorter journey or fewer stops for a known price difference.",
    icon: Layers,
  },
];

const STEPS = [
  {
    n: "01",
    title: "Describe the trip you'd actually take",
    body: "Route, dates, passengers and cabin — plus a budget ceiling and the things you won't compromise on.",
  },
  {
    n: "02",
    title: "See why each pick wins",
    body: "Hard requirements filter first, then preferences rank. If nothing qualifies, SkyScout shows which limit ruled offers out so you can relax it deliberately.",
  },
  {
    n: "03",
    title: "Let SkyScout watch the route",
    body: "Save the search, set a target price, and get one alert per meaningful change — not a stream of noise.",
  },
];

const FEATURES: { title: string; body: string; icon: LucideIcon }[] = [
  {
    title: "Your budget is a rule, not a hint",
    body: "Offers over your ceiling or outside your requirements are never quietly mixed into recommendations.",
    icon: ShieldCheck,
  },
  {
    title: "Explainable ranking",
    body: "Every recommendation lists the factors behind it. Unknown details, like unconfirmed baggage, stay marked as unknown.",
    icon: Sparkles,
  },
  {
    title: "Shared, quota-aware monitoring",
    body: "Identical routes are refreshed once for everyone watching them, on a schedule that respects provider limits.",
    icon: Search,
  },
  {
    title: "Alerts without repeats",
    body: "Price drops and target hits are deduplicated, so the same event never pings you twice.",
    icon: BellRing,
  },
];

const SOURCE_ORDER: FareSource[] = ["live", "cached", "observed", "historical", "demo"];

export default function LandingPage() {
  return (
    <>
      {/* ── Hero ─────────────────────────────────────────────── */}
      <section className="relative isolate overflow-hidden bg-night-900 text-white">
        {/* Horizon falls between the CTAs and the cards so no copy sits on the bright band. */}
        <SkyBackdrop horizon={68} />
        <div className="relative mx-auto grid max-w-6xl gap-12 px-4 pt-20 pb-16 sm:px-6 sm:pt-28 lg:pb-24">
          <div className="max-w-3xl">
            <p className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/25 bg-white/10 px-3 py-1 text-sm backdrop-blur-sm">
              <span className="size-1.5 rounded-full bg-[var(--coral-400)]" aria-hidden />
              Flight price intelligence
            </p>
            <h1 className="font-display text-4xl leading-[1.05] font-semibold tracking-tight sm:text-6xl">
              Find the fare that fits.
              <br />
              <span className="text-[var(--sun-200)]">Then let the sky watch it.</span>
            </h1>
            <p className="mt-6 max-w-xl text-lg text-white/85">
              SkyScout compares flights against your budget and must-haves, explains every
              recommendation, and alerts you when a monitored route reaches your target price.
            </p>
          </div>

          <HeroSearch />

          {/* What the results page delivers — described, not faked. */}
          <div className="grid gap-3 sm:grid-cols-3">
            {PICKS.map(({ title, body, icon: Icon }) => (
              <div
                key={title}
                className="rounded-xl border border-white/15 bg-[rgb(28_17_52/0.55)] p-5 backdrop-blur-md"
              >
                <Icon className="size-5 text-[var(--coral-400)]" aria-hidden />
                <h2 className="mt-3 font-medium">{title}</h2>
                <p className="mt-1 text-sm text-white/75">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ─────────────────────────────────────── */}
      <section id="how-it-works" className="scroll-mt-20 py-20 sm:py-24">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <SectionHeading
            eyebrow="How it works"
            title="From a question to a decision"
            body="SkyScout is built around one journey: search with real constraints, understand the options, and keep watching until the price is right."
          />
          <ol className="mt-12 grid gap-6 md:grid-cols-3">
            {STEPS.map((s) => (
              <li key={s.n} className="relative rounded-xl border border-border bg-surface p-6">
                <span className="font-display text-3xl font-semibold text-primary tabular">
                  {s.n}
                </span>
                <h3 className="mt-4 font-semibold">{s.title}</h3>
                <p className="mt-2 text-sm text-muted">{s.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* ── Data honesty ─────────────────────────────────────── */}
      <section
        id="data-honesty"
        className="scroll-mt-20 border-y border-border bg-surface-2 py-20 sm:py-24"
      >
        <div className="mx-auto grid max-w-6xl gap-12 px-4 sm:px-6 lg:grid-cols-[1fr_1.2fr] lg:items-start">
          <SectionHeading
            eyebrow="Data honesty"
            title="Every price says where it came from"
            body="Fares change by the minute and not every number is a bookable quote. SkyScout labels each price so you know how much to trust it — with an icon and words, never colour alone."
          />
          <ul className="grid gap-3">
            {SOURCE_ORDER.map((s) => (
              <li
                key={s}
                className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-4 sm:flex-row sm:items-center sm:gap-4"
              >
                <SourceBadge source={s} className="w-fit shrink-0" />
                <p className="text-sm text-muted">{SOURCE_DESCRIPTIONS[s].title}.</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* ── Features ─────────────────────────────────────────── */}
      <section id="features" className="scroll-mt-20 py-20 sm:py-24">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <SectionHeading
            eyebrow="Principles"
            title="Built to be trusted with your trip"
            body="The rules SkyScout follows when it searches, ranks and alerts."
          />
          <div className="mt-12 grid gap-6 sm:grid-cols-2">
            {FEATURES.map(({ title, body, icon: Icon }) => (
              <div
                key={title}
                className="flex gap-4 rounded-xl border border-border bg-surface p-6"
              >
                <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-primary-soft text-primary">
                  <Icon className="size-5" aria-hidden />
                </span>
                <div>
                  <h3 className="font-semibold">{title}</h3>
                  <p className="mt-1 text-sm text-muted">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA band ─────────────────────────────────────────── */}
      <section className="px-4 pb-20 sm:px-6 sm:pb-24">
        <div className="relative isolate mx-auto max-w-6xl overflow-hidden rounded-2xl bg-night-900 px-6 py-14 text-white sm:px-12">
          <SkyBackdrop horizon={78} plane={false} />
          <div className="relative max-w-xl">
            <h2 className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">
              Your next fare, watched for you
            </h2>
            <p className="mt-3 text-white/85">
              Create a free account to save searches, set target prices and manage alerts.
            </p>
            <Button asChild variant="accent" size="lg" className="mt-8">
              <Link href="/register">
                Create free account <ArrowRight aria-hidden />
              </Link>
            </Button>
          </div>
        </div>
      </section>
    </>
  );
}

function SectionHeading({
  eyebrow,
  title,
  body,
}: {
  eyebrow: string;
  title: string;
  body: string;
}) {
  return (
    <div className="max-w-2xl">
      <p className="text-sm font-semibold tracking-wide text-accent-text uppercase">{eyebrow}</p>
      <h2 className="mt-2 font-display text-3xl font-semibold tracking-tight sm:text-4xl">
        {title}
      </h2>
      <p className="mt-4 text-muted">{body}</p>
    </div>
  );
}
