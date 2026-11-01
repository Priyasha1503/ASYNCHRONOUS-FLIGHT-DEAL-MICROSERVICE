"use client";

import { Bell, Menu, UserRound, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Logo } from "@/components/site/logo";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/card";
import { useMe } from "@/lib/auth";
import { useUnreadCount } from "@/lib/monitoring";
import { cn } from "@/lib/utils";

const MARKETING_NAV = [
  { href: "/search", label: "Search flights" },
  { href: "/#how-it-works", label: "How it works" },
  { href: "/#data-honesty", label: "Data honesty" },
  { href: "/#features", label: "Features" },
];

const APP_NAV = [
  { href: "/search", label: "Search flights" },
  { href: "/monitors", label: "Monitoring" },
  { href: "/notifications", label: "Alerts" },
];

export function SiteHeader() {
  const { data: me, isPending } = useMe();
  const { data: unread } = useUnreadCount();
  const count = unread?.unread_count ?? 0;
  const [open, setOpen] = useState(false);
  const nav = me ? APP_NAV : MARKETING_NAV;

  const authArea = isPending ? (
    <Skeleton className="h-10 w-36" />
  ) : me ? (
    <>
      <Button asChild variant="ghost" size="icon" className="relative">
        <Link href="/notifications" aria-label={count ? `Alerts, ${count} unread` : "Alerts"}>
          <Bell aria-hidden />
          {count > 0 && (
            <span
              aria-hidden
              className="absolute top-1 right-1 grid min-w-4 place-items-center rounded-full bg-accent px-1 text-[10px] leading-4 font-semibold text-night-950"
            >
              {count > 9 ? "9+" : count}
            </span>
          )}
        </Link>
      </Button>
      <Button asChild variant="secondary">
        <Link href="/account">
          <UserRound aria-hidden />
          {me.display_name || "Account"}
        </Link>
      </Button>
    </>
  ) : (
    <>
      <Button asChild variant="ghost">
        <Link href="/signin">Sign in</Link>
      </Button>
      <Button asChild>
        <Link href="/register">Get started</Link>
      </Button>
    </>
  );

  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-bg/80 backdrop-blur-md">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <Link href="/" aria-label="SkyScout AI home" className="rounded-md">
          <Logo />
        </Link>
        <nav aria-label="Primary" className="hidden items-center gap-1 md:flex">
          {nav.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className="rounded-md px-3 py-2 text-sm text-muted transition-colors hover:bg-surface-2 hover:text-text"
            >
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="hidden items-center gap-2 md:flex">{authArea}</div>
        <Button
          variant="ghost"
          size="icon"
          className="relative md:hidden"
          aria-expanded={open}
          aria-controls="mobile-nav"
          aria-label={
            open ? "Close menu" : count ? `Open menu, ${count} unread alerts` : "Open menu"
          }
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X aria-hidden /> : <Menu aria-hidden />}
          {!open && count > 0 && (
            <span aria-hidden className="absolute top-2 right-2 size-2 rounded-full bg-accent" />
          )}
        </Button>
      </div>
      <div
        id="mobile-nav"
        hidden={!open}
        className={cn("border-t border-border bg-surface px-4 pt-2 pb-4 md:hidden")}
        // Close after any link inside the panel is followed.
        onClick={(e) => {
          if ((e.target as HTMLElement).closest("a")) setOpen(false);
        }}
      >
        <nav aria-label="Mobile" className="grid gap-1">
          {nav.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className="flex items-center justify-between rounded-md px-3 py-2.5 text-text hover:bg-surface-2"
            >
              {n.label}
              {n.href === "/notifications" && count > 0 && (
                <span className="rounded-full bg-accent px-2 text-xs font-semibold text-night-950">
                  {count}
                </span>
              )}
            </Link>
          ))}
        </nav>
        <div className="mt-3 flex gap-2 [&>*]:flex-1">
          {me ? <AccountLink name={me.display_name} /> : authArea}
        </div>
      </div>
    </header>
  );
}

function AccountLink({ name }: { name: string | null }) {
  return (
    <Button asChild variant="secondary">
      <Link href="/account">
        <UserRound aria-hidden />
        {name || "Account"}
      </Link>
    </Button>
  );
}
