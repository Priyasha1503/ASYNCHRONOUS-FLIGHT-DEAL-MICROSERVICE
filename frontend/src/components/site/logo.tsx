import { cn } from "@/lib/utils";

/** Original mark: a setting sun on the horizon with a climbing flight path. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("size-8", className)} aria-hidden>
      <defs>
        <linearGradient id="ss-sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#6b3fd4" />
          <stop offset="1" stopColor="#3c2770" />
        </linearGradient>
        <linearGradient id="ss-sun" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffd9b0" />
          <stop offset="1" stopColor="#f26b4a" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="url(#ss-sky)" />
      <path d="M8 21a8 8 0 0 1 16 0z" fill="url(#ss-sun)" />
      <path d="M5 21.5h22" stroke="#f7f3ff" strokeWidth="1.5" strokeLinecap="round" />
      <path
        d="M7 15.5c5-.4 10.5-3 17-8.5"
        stroke="#f7f3ff"
        strokeWidth="1.6"
        strokeLinecap="round"
        fill="none"
        strokeDasharray="0.1 3.2"
      />
      <path d="m24.8 6.2-3.9.7 1.6 1.3-.6 2z" fill="#f7f3ff" />
    </svg>
  );
}

export function Logo({
  className,
  tone = "default",
}: {
  className?: string;
  tone?: "default" | "light";
}) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LogoMark />
      <span
        className={cn(
          "font-display text-xl font-semibold tracking-tight",
          tone === "light" ? "text-white" : "text-text",
        )}
      >
        SkyScout
        <span
          className={cn(
            "ml-1 text-sm font-medium",
            tone === "light" ? "text-white/70" : "text-accent-text",
          )}
        >
          AI
        </span>
      </span>
    </span>
  );
}
