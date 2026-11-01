"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { z } from "zod";

import { api } from "@/lib/api";

export type Preferences = {
  currency: string;
  home_airport: string | null;
  timezone: string;
  email_notifications: boolean;
  inapp_notifications: boolean;
};

export type User = {
  id: string;
  email: string;
  display_name: string | null;
  created_at: string;
  preferences: Preferences;
};

// Mirrors backend validation (app/api/v1/schemas/auth.py); the backend remains authoritative.
export const registerSchema = z.object({
  display_name: z.string().trim().max(80, "Keep it under 80 characters").optional(),
  email: z.email("Enter a valid email address"),
  password: z.string().min(10, "Use at least 10 characters").max(128, "Use at most 128 characters"),
});
export type RegisterInput = z.infer<typeof registerSchema>;

export const loginSchema = z.object({
  email: z.email("Enter a valid email address"),
  password: z.string().min(1, "Enter your password"),
});
export type LoginInput = z.infer<typeof loginSchema>;

export const preferencesSchema = z.object({
  currency: z.string().regex(/^[A-Za-z]{3}$/, "3-letter ISO code, e.g. USD"),
  home_airport: z
    .string()
    .regex(/^([A-Za-z]{3})?$/, "3-letter IATA code, e.g. LHR")
    .transform((v) => (v ? v.toUpperCase() : null)),
  timezone: z.string().min(1, "Choose a timezone"),
  email_notifications: z.boolean(),
  inapp_notifications: z.boolean(),
});
export type PreferencesForm = z.input<typeof preferencesSchema>;
export type PreferencesValues = z.output<typeof preferencesSchema>;

const ME = ["me"] as const;

export function useMe() {
  return useQuery({
    queryKey: ME,
    queryFn: async () => (await api<{ user: User | null }>("/auth/session")).user,
    staleTime: 60_000,
    retry: false,
  });
}

/** For signed-in-only pages: redirects anonymous visitors to sign-in and back. The backend still
 * enforces auth on every request — this is navigation, not authorization. */
export function useRequireUser() {
  const me = useMe();
  const router = useRouter();
  useEffect(() => {
    if (!me.isPending && !me.isError && me.data === null) {
      router.replace(`/signin?next=${encodeURIComponent(location.pathname + location.search)}`);
    }
  }, [me.isPending, me.isError, me.data, router]);
  return me;
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: LoginInput) => api<User>("/auth/login", { method: "POST", body }),
    onSuccess: (user) => qc.setQueryData(ME, user),
  });
}

export function useRegister() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RegisterInput) =>
      api<User>("/auth/register", {
        method: "POST",
        body: { ...body, display_name: body.display_name || null },
      }),
    onSuccess: (user) => qc.setQueryData(ME, user),
  });
}

/**
 * Ends the session server-side, then does a full page load to `to`. A hard navigation discards all
 * cached user data in memory, and avoids racing auth-guard redirects on the page being left.
 */
export function useLogout(to = "/") {
  return useMutation({
    mutationFn: () => api<void>("/auth/logout", { method: "POST" }),
    onSuccess: () => window.location.assign(to),
  });
}

export function useUpdatePreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PreferencesValues) =>
      api<User>("/me/preferences", { method: "PATCH", body }),
    onSuccess: (user) => qc.setQueryData(ME, user),
  });
}

export function useDeleteAccount(to = "/?account=deleted") {
  return useMutation({
    mutationFn: (password: string) => api<void>("/me", { method: "DELETE", body: { password } }),
    onSuccess: () => window.location.assign(to),
  });
}
