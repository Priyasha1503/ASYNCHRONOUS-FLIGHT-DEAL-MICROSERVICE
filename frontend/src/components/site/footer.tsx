import Link from "next/link";

import { Logo } from "@/components/site/logo";

export function SiteFooter() {
  return (
    <footer className="border-t border-border bg-surface">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 sm:px-6 md:grid-cols-[1.4fr_1fr_1fr]">
        <div className="grid content-start gap-3">
          <Logo />
          <p className="max-w-sm text-sm text-muted">
            Flight price intelligence that respects your budget and tells you where every number
            came from. SkyScout links out to providers for booking; it does not sell tickets.
          </p>
        </div>
        <nav aria-label="Product" className="grid content-start gap-2 text-sm">
          <p className="font-medium">Product</p>
          <Link className="text-muted hover:text-text" href="/#how-it-works">
            How it works
          </Link>
          <Link className="text-muted hover:text-text" href="/#data-honesty">
            Data honesty
          </Link>
          <Link className="text-muted hover:text-text" href="/#features">
            Features
          </Link>
        </nav>
        <nav aria-label="Account" className="grid content-start gap-2 text-sm">
          <p className="font-medium">Account</p>
          <Link className="text-muted hover:text-text" href="/register">
            Create account
          </Link>
          <Link className="text-muted hover:text-text" href="/signin">
            Sign in
          </Link>
          <Link className="text-muted hover:text-text" href="/account">
            Settings
          </Link>
        </nav>
      </div>
      <div className="border-t border-border">
        <p className="mx-auto max-w-6xl px-4 py-4 text-xs text-subtle sm:px-6">
          Prices shown by SkyScout are search results, not guaranteed checkout prices. Always
          confirm the final fare with the provider. Booking links to airlines and travel agencies
          are affiliate links: SkyScout may earn a commission, at no extra cost to you.
        </p>
      </div>
    </footer>
  );
}
