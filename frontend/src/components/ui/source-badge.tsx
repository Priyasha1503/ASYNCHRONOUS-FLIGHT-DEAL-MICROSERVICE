import { Clock3, Eye, FlaskConical, History, Radio, type LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

/** Data-honesty labels from docs/PRD.md §4. Always icon + text — never colour alone. */
export type FareSource = "live" | "cached" | "observed" | "historical" | "demo";

const SOURCES: Record<
  FareSource,
  { label: string; icon: LucideIcon; tone: string; title: string }
> = {
  live: {
    label: "Live",
    icon: Radio,
    tone: "bg-success-soft text-success",
    title: "Returned by a provider's real-time search for this request",
  },
  cached: {
    label: "Cached",
    icon: Clock3,
    tone: "bg-info-soft text-info",
    title: "A recent live result reused from the shared cache",
  },
  observed: {
    label: "Observed",
    icon: Eye,
    tone: "bg-primary-soft text-primary",
    title: "A fare a provider recently saw — not a bookable quote",
  },
  historical: {
    label: "Historical",
    icon: History,
    tone: "bg-surface-2 text-muted",
    title: "A price SkyScout stored earlier, shown for history only",
  },
  demo: {
    label: "Demo data",
    icon: FlaskConical,
    tone: "bg-accent-soft text-accent-text",
    title: "Deterministic sample data — not a real fare",
  },
};

export function SourceBadge({
  source,
  detail,
  className,
}: {
  source: FareSource;
  detail?: string;
  className?: string;
}) {
  const s = SOURCES[source];
  const Icon = s.icon;
  return (
    <span
      title={s.title}
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        s.tone,
        className,
      )}
    >
      <Icon className="size-3" aria-hidden />
      {s.label}
      {detail && <span className="font-normal opacity-80">· {detail}</span>}
    </span>
  );
}

export const SOURCE_DESCRIPTIONS = SOURCES;
