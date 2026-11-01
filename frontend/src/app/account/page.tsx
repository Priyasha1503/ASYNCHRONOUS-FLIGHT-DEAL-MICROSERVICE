"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Skeleton,
} from "@/components/ui/card";
import { Field, Input, Label, Switch } from "@/components/ui/field";
import { FormAlert } from "@/components/ui/form-alert";
import { ApiError } from "@/lib/api";
import {
  preferencesSchema,
  useDeleteAccount,
  useLogout,
  useMe,
  useUpdatePreferences,
  type PreferencesForm,
  type PreferencesValues,
  type User,
} from "@/lib/auth";
import { applyServerErrors } from "@/lib/form-errors";

const CURRENCIES = ["USD", "EUR", "GBP", "INR", "AUD", "CAD", "SGD", "AED", "JPY", "CHF"];

export default function AccountPage() {
  const router = useRouter();
  const { data: me, isPending, isError, refetch } = useMe();

  useEffect(() => {
    if (!isPending && !isError && me === null) router.replace("/signin?next=/account");
  }, [isPending, isError, me, router]);

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6 sm:py-14">
      <h1 className="font-display text-3xl font-semibold tracking-tight">Account settings</h1>
      <p className="mt-2 text-muted">Your profile, defaults and notification preferences.</p>
      <div className="mt-8 grid gap-6">
        {isError ? (
          <Card>
            <CardContent className="grid gap-3 pt-5 sm:pt-6">
              <FormAlert message="We couldn't load your account. The service may be unavailable." />
              <Button variant="secondary" className="w-fit" onClick={() => void refetch()}>
                Try again
              </Button>
            </CardContent>
          </Card>
        ) : !me ? (
          <AccountSkeleton />
        ) : (
          <>
            <ProfileCard user={me} />
            <PreferencesCard user={me} />
            <DangerZone />
          </>
        )}
      </div>
    </div>
  );
}

function AccountSkeleton() {
  return (
    <>
      {[120, 380, 160].map((h) => (
        <Card key={h} className="p-6">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="mt-3 h-4 w-64" />
          <Skeleton className="mt-6 w-full" style={{ height: h - 80 }} />
        </Card>
      ))}
    </>
  );
}

function ProfileCard({ user }: { user: User }) {
  const logout = useLogout();
  const joined = new Date(user.created_at).toLocaleDateString(undefined, { dateStyle: "long" });
  return (
    <Card>
      <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <span
            aria-hidden
            className="grid size-12 place-items-center rounded-full bg-primary-soft font-display text-lg font-semibold text-primary"
          >
            {(user.display_name || user.email).slice(0, 1).toUpperCase()}
          </span>
          <div>
            <CardTitle>{user.display_name || "Traveller"}</CardTitle>
            <CardDescription>
              {user.email} · Member since {joined}
            </CardDescription>
          </div>
        </div>
        <Button
          variant="secondary"
          loading={logout.isPending || logout.isSuccess}
          onClick={() =>
            logout.mutate(undefined, {
              onError: () => toast.error("Couldn't sign out. Check your connection and retry."),
            })
          }
        >
          <LogOut aria-hidden /> Sign out
        </Button>
      </CardHeader>
    </Card>
  );
}

function PreferencesCard({ user }: { user: User }) {
  const update = useUpdatePreferences();
  const [formError, setFormError] = useState<string | null>(null);
  const timezones = useMemo(() => {
    const zones = Intl.supportedValuesOf?.("timeZone") ?? [];
    return zones.includes("UTC") ? zones : ["UTC", ...zones];
  }, []);

  const defaults: PreferencesForm = {
    currency: user.preferences.currency,
    home_airport: user.preferences.home_airport ?? "",
    timezone: user.preferences.timezone,
    email_notifications: user.preferences.email_notifications,
    inapp_notifications: user.preferences.inapp_notifications,
  };
  const {
    register,
    control,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isDirty },
  } = useForm<PreferencesForm, unknown, PreferencesValues>({
    resolver: zodResolver(preferencesSchema),
    defaultValues: defaults,
  });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      const updated = await update.mutateAsync({
        ...values,
        currency: values.currency.toUpperCase(),
      });
      reset({
        ...updated.preferences,
        home_airport: updated.preferences.home_airport ?? "",
      });
      toast.success("Preferences saved");
    } catch (e) {
      setFormError(
        e instanceof ApiError && e.status === 400
          ? e.message
          : applyServerErrors(e, setError, ["currency", "home_airport", "timezone"]),
      );
    }
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Preferences</CardTitle>
        <CardDescription>Defaults for new searches and how SkyScout reaches you.</CardDescription>
      </CardHeader>
      <CardContent>
        <form noValidate onSubmit={onSubmit} className="grid gap-6">
          <FormAlert message={formError} />
          <div className="grid gap-5 sm:grid-cols-3">
            <Field id="currency" label="Currency" error={errors.currency?.message}>
              {(a) => (
                <select
                  {...a}
                  {...register("currency")}
                  className="h-10 w-full rounded-md border border-border-strong bg-surface px-3 text-sm shadow-sm focus-visible:border-primary"
                >
                  {[...new Set([user.preferences.currency, ...CURRENCIES])].map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              )}
            </Field>
            <Field
              id="home_airport"
              label="Home airport"
              hint="IATA code, e.g. LHR"
              error={errors.home_airport?.message}
            >
              {(a) => (
                <Input
                  {...a}
                  maxLength={3}
                  autoCapitalize="characters"
                  className="uppercase"
                  placeholder="—"
                  {...register("home_airport")}
                />
              )}
            </Field>
            <Field id="timezone" label="Timezone" error={errors.timezone?.message}>
              {(a) => (
                <select
                  {...a}
                  {...register("timezone")}
                  className="h-10 w-full rounded-md border border-border-strong bg-surface px-3 text-sm shadow-sm focus-visible:border-primary"
                >
                  {timezones.map((z) => (
                    <option key={z}>{z}</option>
                  ))}
                </select>
              )}
            </Field>
          </div>

          <fieldset className="grid gap-4 rounded-lg border border-border p-4">
            <legend className="px-1 text-sm font-medium">Notifications</legend>
            {(
              [
                ["inapp_notifications", "In-app alerts", "Price alerts in your SkyScout inbox."],
                [
                  "email_notifications",
                  "Email alerts",
                  "Sent once email delivery is configured for this deployment.",
                ],
              ] as const
            ).map(([name, label, hint]) => (
              <Controller
                key={name}
                control={control}
                name={name}
                render={({ field }) => (
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <Label htmlFor={name}>{label}</Label>
                      <p className="text-sm text-muted">{hint}</p>
                    </div>
                    <Switch id={name} checked={field.value} onCheckedChange={field.onChange} />
                  </div>
                )}
              />
            ))}
          </fieldset>

          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="ghost"
              disabled={!isDirty}
              onClick={() => reset(defaults)}
            >
              Discard
            </Button>
            <Button type="submit" disabled={!isDirty} loading={update.isPending}>
              Save preferences
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function DangerZone() {
  const del = useDeleteAccount();
  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  return (
    <Card className="border-danger/30">
      <CardHeader>
        <CardTitle>Delete account</CardTitle>
        <CardDescription>
          Permanently removes your account, sessions and preferences. This can&apos;t be undone.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!confirming ? (
          <Button variant="secondary" className="text-danger" onClick={() => setConfirming(true)}>
            Delete my account…
          </Button>
        ) : (
          <form
            className="grid gap-4 sm:max-w-sm"
            onSubmit={(e) => {
              e.preventDefault();
              setError(null);
              del.mutate(password, {
                onError: (err) =>
                  setError(err instanceof ApiError ? err.message : "Couldn't delete the account"),
              });
            }}
          >
            <FormAlert message={error} />
            <Field id="confirm_password" label="Confirm with your password">
              {(a) => (
                <Input
                  {...a}
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoFocus
                />
              )}
            </Field>
            <div className="flex gap-2">
              <Button type="submit" variant="danger" disabled={!password} loading={del.isPending}>
                Permanently delete
              </Button>
              <Button type="button" variant="ghost" onClick={() => setConfirming(false)}>
                Cancel
              </Button>
            </div>
          </form>
        )}
      </CardContent>
    </Card>
  );
}
