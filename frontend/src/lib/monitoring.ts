"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useMe } from "@/lib/auth";

// Mirrors backend/app/api/v1/schemas/monitoring.py
export type MonitorStatus = "active" | "paused" | "departed";

export type Monitor = {
  id: string;
  name: string;
  status: MonitorStatus;
  search: Record<string, unknown>;
  origin: string;
  destination: string;
  depart_date: string;
  return_date: string | null;
  currency: string;
  target_price: string | null;
  drop_threshold_pct: string | null;
  notify_new_qualifying: boolean;
  frequency_minutes: number;
  effective_interval_minutes: number;
  created_at: string;
  last_checked_at: string | null;
  next_check_at: string | null;
  last_price: string | null;
  last_qualifying: number | null;
  best_price: string | null;
  best_price_at: string | null;
};

export type RefreshRun = {
  id: string;
  slot: string;
  trigger: "schedule" | "manual";
  status: "running" | "succeeded" | "partial" | "failed";
  started_at: string;
  finished_at: string | null;
  offers_count: number | null;
  providers: { provider: string; state: string; offers: number; message: string | null }[] | null;
  error: string | null;
};

export type HistoryPoint = {
  checked_at: string;
  observed_at: string | null;
  cheapest_amount: string | null;
  qualifying: number;
  total: number;
  source: string | null;
};

export type MonitorDetail = Monitor & {
  runs: RefreshRun[];
  history: HistoryPoint[];
  demo_simulation_available: boolean;
};

export type AppNotification = {
  id: string;
  rule_id: string | null;
  kind: "below_target" | "price_drop" | "now_available" | string;
  title: string;
  body: string;
  data: Record<string, string | null>;
  created_at: string;
  read_at: string | null;
};

export const FREQUENCIES: { value: number; label: string }[] = [
  { value: 60, label: "Hourly" },
  { value: 360, label: "Every 6 hours" },
  { value: 720, label: "Every 12 hours" },
  { value: 1440, label: "Daily" },
];

export type CreateMonitorBody = {
  search: unknown;
  name?: string;
  target_price: string | null;
  drop_threshold_pct: string | null;
  notify_new_qualifying: boolean;
  frequency_minutes: number;
};

export type UpdateMonitorBody = Partial<{
  name: string;
  target_price: string | null;
  drop_threshold_pct: string | null;
  notify_new_qualifying: boolean;
  frequency_minutes: number;
  is_active: boolean;
}>;

const KEYS = {
  monitors: ["monitors"] as const,
  monitor: (id: string) => ["monitors", id] as const,
  notifications: ["notifications"] as const,
  unread: ["notifications", "unread"] as const,
};

export function useMonitors() {
  return useQuery({ queryKey: KEYS.monitors, queryFn: () => api<Monitor[]>("/monitors") });
}

/** Polls while a check is likely in flight (just created / manual check), otherwise every minute. */
export function useMonitor(id: string, { fast = false }: { fast?: boolean } = {}) {
  return useQuery({
    queryKey: KEYS.monitor(id),
    queryFn: () => api<MonitorDetail>(`/monitors/${id}`),
    refetchInterval: fast ? 3000 : 60_000,
    retry: false,
  });
}

function useInvalidateAll() {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: KEYS.monitors });
    void qc.invalidateQueries({ queryKey: KEYS.notifications });
  };
}

export function useCreateMonitor() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (body: CreateMonitorBody) => api<Monitor>("/monitors", { method: "POST", body }),
    onSuccess: invalidate,
  });
}

export function useUpdateMonitor(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: UpdateMonitorBody) =>
      api<Monitor>(`/monitors/${id}`, { method: "PATCH", body }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: KEYS.monitors }),
  });
}

export function useDeleteMonitor() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (id: string) => api<void>(`/monitors/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });
}

export function useCheckNow(id: string) {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: () =>
      api<{ status: string; message: string }>(`/monitors/${id}/refresh`, { method: "POST" }),
    onSuccess: invalidate,
  });
}

export function useSimulatePriceChange(id: string) {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (percent: number) =>
      api<{ status: string; message: string }>(`/monitors/${id}/simulate-price-change`, {
        method: "POST",
        body: { percent: percent.toFixed(1) },
      }),
    onSuccess: invalidate,
  });
}

type NotificationPage = {
  items: AppNotification[];
  next_cursor: string | null;
  unread_count: number;
};

export function useNotifications() {
  return useInfiniteQuery({
    queryKey: KEYS.notifications,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      api<NotificationPage>(
        `/notifications?limit=20${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ""}`,
      ),
    getNextPageParam: (last) => last.next_cursor,
  });
}

export function useUnreadCount() {
  const { data: me } = useMe();
  return useQuery({
    queryKey: KEYS.unread,
    queryFn: () => api<{ unread_count: number }>("/notifications/unread-count"),
    enabled: !!me,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useMarkRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api<AppNotification>(`/notifications/${id}/read`, { method: "POST" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: KEYS.notifications }),
  });
}

export function useMarkAllRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<{ unread_count: number }>("/notifications/read-all", { method: "POST" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: KEYS.notifications }),
  });
}
