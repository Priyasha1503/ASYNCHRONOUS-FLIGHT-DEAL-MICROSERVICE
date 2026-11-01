"use client";

import { BellOff, CheckCheck, TrendingDown, Target, Sparkles } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, Skeleton } from "@/components/ui/card";
import { FormAlert } from "@/components/ui/form-alert";
import { useRequireUser } from "@/lib/auth";
import { relativeTime } from "@/lib/format";
import {
  useMarkAllRead,
  useMarkRead,
  useNotifications,
  type AppNotification,
} from "@/lib/monitoring";
import { cn } from "@/lib/utils";

const KIND = {
  below_target: { icon: Target, label: "Target reached" },
  price_drop: { icon: TrendingDown, label: "Price drop" },
  now_available: { icon: Sparkles, label: "Now available" },
} as const;

export default function NotificationsPage() {
  const me = useRequireUser();
  const q = useNotifications();
  const markAll = useMarkAllRead();
  const items = q.data?.pages.flatMap((p) => p.items) ?? [];
  const unread = q.data?.pages[0]?.unread_count ?? 0;

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-tight">Alerts</h1>
          <p className="mt-2 text-muted">
            {unread ? `${unread} unread.` : "You're all caught up."} Email copies follow your{" "}
            <Link href="/account" className="text-primary hover:underline">
              notification settings
            </Link>
            .
          </p>
        </div>
        <Button
          variant="secondary"
          disabled={!unread}
          loading={markAll.isPending}
          onClick={() => markAll.mutate()}
        >
          <CheckCheck aria-hidden /> Mark all read
        </Button>
      </div>

      <div className="mt-8 grid gap-3">
        {me.isPending || q.isPending ? (
          [0, 1, 2].map((i) => <Skeleton key={i} className="h-24 rounded-xl" />)
        ) : q.isError ? (
          <FormAlert message="Couldn't load alerts." />
        ) : items.length === 0 ? (
          <Card className="grid justify-items-start gap-3 p-8">
            <span className="grid size-12 place-items-center rounded-full bg-surface-2 text-muted">
              <BellOff className="size-6" aria-hidden />
            </span>
            <h2 className="text-xl font-semibold">No alerts yet</h2>
            <p className="max-w-prose text-muted">
              When a monitored trip reaches your target, drops meaningfully, or starts having
              qualifying flights, the alert lands here — once per event.
            </p>
            <Button asChild variant="secondary">
              <Link href="/monitors">Go to monitoring</Link>
            </Button>
          </Card>
        ) : (
          <>
            {items.map((n) => (
              <NotificationRow key={n.id} n={n} />
            ))}
            {q.hasNextPage && (
              <Button
                variant="secondary"
                loading={q.isFetchingNextPage}
                onClick={() => void q.fetchNextPage()}
              >
                Load older alerts
              </Button>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function NotificationRow({ n }: { n: AppNotification }) {
  const read = useMarkRead();
  const k = KIND[n.kind as keyof typeof KIND] ?? { icon: Target, label: n.kind };
  const Icon = k.icon;
  const unread = n.read_at === null;
  return (
    <article
      className={cn(
        "flex gap-4 rounded-xl border bg-surface p-5",
        unread ? "border-primary/40 shadow-sm" : "border-border",
      )}
    >
      <span
        className={cn(
          "grid size-10 shrink-0 place-items-center rounded-full",
          unread ? "bg-primary-soft text-primary" : "bg-surface-2 text-muted",
        )}
      >
        <Icon className="size-5" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-xs text-muted">
          {k.label} · {relativeTime(n.created_at)}
          {unread && (
            <span className="ml-2 rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-semibold text-primary-fg">
              NEW
            </span>
          )}
        </p>
        <h2 className="mt-1 font-semibold">{n.title}</h2>
        <p className="mt-1 text-sm text-muted">{n.body}</p>
        <div className="mt-3 flex flex-wrap gap-3 text-sm">
          {n.rule_id && (
            <Link
              href={`/monitors/${n.rule_id}`}
              className="font-medium text-primary hover:underline"
              onClick={() => unread && read.mutate(n.id)}
            >
              Open monitor
            </Link>
          )}
          {unread && (
            <button className="text-muted hover:text-text" onClick={() => read.mutate(n.id)}>
              Mark as read
            </button>
          )}
        </div>
      </div>
    </article>
  );
}
