import { SkyBackdrop } from "@/components/site/sky-backdrop";

export function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  footer: React.ReactNode;
}) {
  return (
    <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 lg:grid-cols-2 lg:py-16">
      <div className="mx-auto w-full max-w-md">
        <h1 className="font-display text-3xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-2 text-muted">{subtitle}</p>
        <div className="mt-8">{children}</div>
        <div className="mt-6 text-sm text-muted">{footer}</div>
      </div>
      <aside
        aria-hidden
        className="relative isolate hidden min-h-[480px] overflow-hidden rounded-2xl bg-night-900 lg:block"
      >
        <SkyBackdrop horizon={64} />
        <div className="absolute inset-x-8 bottom-8 text-white">
          <p className="font-display text-2xl leading-snug">
            “Cheapest” only counts if it meets your requirements.
          </p>
          <p className="mt-2 text-sm text-white/75">
            SkyScout filters on your hard limits before it ranks anything.
          </p>
        </div>
      </aside>
    </div>
  );
}
