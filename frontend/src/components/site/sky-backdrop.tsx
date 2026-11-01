import { cn } from "@/lib/utils";

/**
 * Pure-CSS twilight sky (no raster assets): periwinkle upper sky → magenta/coral cloud bands →
 * lavender horizon glow → deep violet sea with a sun reflection. Interprets design-references/
 * reference1 (sea horizon) and reference2/3 (magenta-coral dusk clouds).
 */
export function SkyBackdrop({
  className,
  horizon = 62,
  scrim = true,
  plane = true,
}: {
  className?: string;
  /** Horizon position as a % from the top. */
  horizon?: number;
  scrim?: boolean;
  plane?: boolean;
}) {
  const h = horizon;
  return (
    <div
      aria-hidden
      className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}
    >
      {/* Sky + sea base */}
      <div
        className="absolute inset-0"
        style={{
          background: `linear-gradient(180deg,
            #4d5bb8 0%, #7a6fd0 ${h * 0.35}%, #b77fcb ${h * 0.7}%, #eaa0bd ${h * 0.92}%,
            #f8c7c9 ${h - 0.4}%, #fbe3da ${h}%, #7b4aa6 ${h + 0.3}%, #4a2d84 ${h + 8}%,
            #2a1a4d ${h + 24}%, #1c1134 100%)`,
        }}
      />
      {/* Cloud streaks (refs 1–3): soft, diagonal, magenta → coral */}
      <div
        className="absolute inset-0 opacity-90 mix-blend-screen"
        style={{
          top: 0,
          height: `${h}%`,
          background: `
            radial-gradient(60% 18% at 22% 28%, rgb(255 138 170 / 0.55), transparent 70%),
            radial-gradient(45% 12% at 70% 18%, rgb(255 150 120 / 0.45), transparent 70%),
            radial-gradient(55% 14% at 58% 46%, rgb(244 110 160 / 0.5), transparent 70%),
            radial-gradient(35% 10% at 12% 60%, rgb(255 170 140 / 0.4), transparent 70%),
            radial-gradient(40% 12% at 88% 62%, rgb(230 120 190 / 0.45), transparent 70%)`,
          filter: "blur(6px)",
          transform: "skewY(-6deg)",
          transformOrigin: "left",
        }}
      />
      {/* Sun glow on the horizon */}
      <div
        className="absolute left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full"
        style={{
          top: `${h}%`,
          width: "min(70vw, 900px)",
          height: "220px",
          background:
            "radial-gradient(closest-side, rgb(255 205 170 / 0.75), rgb(242 107 74 / 0.25) 55%, transparent)",
        }}
      />
      {/* Reflection column on the sea */}
      <div
        className="absolute left-1/2 -translate-x-1/2"
        style={{
          top: `${h}%`,
          bottom: 0,
          width: "min(26vw, 320px)",
          background:
            "linear-gradient(180deg, rgb(217 64 126 / 0.45), rgb(217 64 126 / 0.08) 70%, transparent)",
          filter: "blur(18px)",
        }}
      />
      {plane && (
        <svg
          className="sky-plane absolute hidden w-[min(46vw,520px)] sm:block"
          style={{ top: `${h * 0.18}%`, right: "6%" }}
          viewBox="0 0 520 120"
          fill="none"
        >
          <path
            d="M2 118 C 140 100, 300 60, 470 14"
            stroke="url(#contrail)"
            strokeWidth="2"
            strokeLinecap="round"
          />
          <defs>
            <linearGradient id="contrail" x1="0" x2="1">
              <stop offset="0" stopColor="#fff" stopOpacity="0" />
              <stop offset="1" stopColor="#fff" stopOpacity="0.85" />
            </linearGradient>
          </defs>
          {/* Small stylised aircraft silhouette */}
          <g transform="translate(470 14) rotate(-16)" fill="#fff">
            <path d="M-14 0 C -10 -2.2, 14 -2.2, 20 0 C 14 2.2, -10 2.2, -14 0 Z" />
            <path d="M2 -1.2 L -6 -12 L -1.5 -12 L 9 -1.2 Z" opacity="0.92" />
            <path d="M2 1.2 L -4 8 L -0.5 8 L 8 1.2 Z" opacity="0.8" />
            <path d="M-12 -0.6 L -16 -6 L -13.2 -6 L -9 -0.6 Z" />
          </g>
        </svg>
      )}
      {/* Legibility scrim for foreground text */}
      {scrim && (
        <div
          className="absolute inset-0"
          style={{
            background: `linear-gradient(180deg, rgb(18 10 34 / 0.6) 0%, rgb(18 10 34 / 0.4) ${h * 0.6}%, rgb(18 10 34 / 0.15) ${h - 4}%, transparent ${h}%, rgb(18 10 34 / 0.2) 100%)`,
          }}
        />
      )}
    </div>
  );
}
