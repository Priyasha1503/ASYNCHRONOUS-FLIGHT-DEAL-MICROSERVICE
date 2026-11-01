"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeftRight, ChevronDown, Search, SlidersHorizontal } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useId, useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";

import { AirportCombobox } from "@/components/search/airport-combobox";
import { PassengersPicker } from "@/components/search/passengers-picker";
import { Button } from "@/components/ui/button";
import { Field, Input, Label, Switch } from "@/components/ui/field";
import {
  CABINS,
  CURRENCIES,
  TIME_WINDOWS,
  searchSchema,
  toParams,
  type SearchFormInput,
  type SearchValues,
} from "@/lib/search";
import { cn } from "@/lib/utils";

const selectClass =
  "h-11 w-full rounded-md border border-border-strong bg-surface px-3 text-sm text-text shadow-sm focus-visible:border-primary";

export function SearchForm({
  defaultValues,
  sort,
  className,
  submitLabel = "Search flights",
  showAdvanced = false,
  onSubmitted,
}: {
  defaultValues: SearchFormInput;
  sort?: string;
  className?: string;
  submitLabel?: string;
  showAdvanced?: boolean;
  onSubmitted?: () => void;
}) {
  const router = useRouter();
  const uid = useId();
  const [advanced, setAdvanced] = useState(showAdvanced);
  const {
    register,
    control,
    handleSubmit,
    setValue,
    getValues,
    reset,
    formState: { errors, isDirty, isSubmitting },
  } = useForm<SearchFormInput, unknown, SearchValues>({
    resolver: zodResolver(searchSchema),
    defaultValues,
    mode: "onSubmit",
    reValidateMode: "onChange",
  });

  // Late-arriving defaults (e.g. the user's currency once /auth/session resolves) only apply to an
  // untouched form.
  useEffect(() => {
    if (!isDirty) reset(defaultValues);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(defaultValues)]);

  // useWatch (not watch) so the React Compiler can memoize safely.
  const [tripType, departWindow, adults, children, infants] = useWatch({
    control,
    name: ["tripType", "departWindow", "adults", "children", "infants"],
  });
  const id = (name: string) => `${uid}-${name}`;

  const onSubmit = handleSubmit((values) => {
    router.push(`/search?${toParams(values, sort).toString()}`);
    onSubmitted?.();
  });

  return (
    <form
      noValidate
      onSubmit={onSubmit}
      aria-label="Flight search"
      className={cn(
        "rounded-xl border border-border bg-surface p-4 text-text shadow-lg sm:p-5",
        className,
      )}
    >
      {/* Trip type · cabin · currency */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div
          role="radiogroup"
          aria-label="Trip type"
          className="inline-flex rounded-md bg-surface-2 p-1"
        >
          {(
            [
              ["round_trip", "Round trip"],
              ["one_way", "One way"],
            ] as const
          ).map(([value, label]) => (
            <label
              key={value}
              className={cn(
                "cursor-pointer rounded px-3 py-1.5 text-sm font-medium transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
                tripType === value
                  ? "bg-surface text-text shadow-sm"
                  : "text-muted hover:text-text",
              )}
            >
              <input type="radio" value={value} className="sr-only" {...register("tripType")} />
              {label}
            </label>
          ))}
        </div>
        <label className="sr-only" htmlFor={id("cabin")}>
          Cabin class
        </label>
        <select id={id("cabin")} {...register("cabin")} className={cn(selectClass, "h-9 w-auto")}>
          {CABINS.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
        <label className="sr-only" htmlFor={id("currency")}>
          Currency
        </label>
        <select
          id={id("currency")}
          {...register("currency")}
          className={cn(selectClass, "h-9 w-auto")}
        >
          {CURRENCIES.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
      </div>

      {/* Route · dates · passengers */}
      <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr] lg:grid-cols-[1fr_auto_1fr_9.5rem_9.5rem_11rem]">
        <Controller
          control={control}
          name="origin"
          render={({ field }) => (
            <AirportCombobox
              id={id("origin")}
              label="From"
              kind="origin"
              value={field.value}
              onChange={field.onChange}
              onBlur={field.onBlur}
              error={errors.origin?.message}
            />
          )}
        />
        <button
          type="button"
          aria-label="Swap origin and destination"
          onClick={() => {
            const { origin, destination } = getValues();
            setValue("origin", destination, { shouldDirty: true });
            setValue("destination", origin, { shouldDirty: true });
          }}
          className="mx-auto grid size-9 place-items-center self-end rounded-full border border-border-strong bg-surface text-muted transition-colors hover:bg-surface-2 hover:text-text md:mb-1"
        >
          <ArrowLeftRight className="size-4" aria-hidden />
        </button>
        <Controller
          control={control}
          name="destination"
          render={({ field }) => (
            <AirportCombobox
              id={id("destination")}
              label="To"
              kind="destination"
              value={field.value}
              onChange={field.onChange}
              onBlur={field.onBlur}
              error={errors.destination?.message}
            />
          )}
        />
        <Field id={id("depart")} label="Depart" error={errors.depart?.message}>
          {(a) => <Input {...a} type="date" className="h-11" {...register("depart")} />}
        </Field>
        <Field
          id={id("ret")}
          label="Return"
          error={tripType === "round_trip" ? errors.ret?.message : undefined}
        >
          {(a) => (
            <Input
              {...a}
              type="date"
              className="h-11"
              disabled={tripType !== "round_trip"}
              {...register("ret")}
            />
          )}
        </Field>
        <Controller
          control={control}
          name="adults"
          render={() => (
            <PassengersPicker
              value={{
                adults,
                children,
                infants,
              }}
              onChange={(v) => {
                setValue("adults", v.adults, { shouldDirty: true });
                setValue("children", v.children, { shouldDirty: true });
                setValue("infants", v.infants, { shouldDirty: true });
              }}
              error={errors.adults?.message || errors.infants?.message}
            />
          )}
        />
      </div>

      {/* Budget · options · submit */}
      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
        <Field
          id={id("budget")}
          label="Budget (total, optional)"
          error={errors.maxPrice?.message}
          className="sm:w-56"
        >
          {(a) => (
            <Input {...a} inputMode="decimal" placeholder="No limit" {...register("maxPrice")} />
          )}
        </Field>
        <Button
          type="button"
          variant="ghost"
          aria-expanded={advanced}
          aria-controls={id("advanced")}
          onClick={() => setAdvanced((v) => !v)}
          className="justify-start sm:mb-0"
        >
          <SlidersHorizontal aria-hidden /> More options
          <ChevronDown
            aria-hidden
            className={cn(
              "transition-transform duration-[var(--dur-base)]",
              advanced && "rotate-180",
            )}
          />
        </Button>
        <Button type="submit" size="lg" loading={isSubmitting} className="sm:ml-auto sm:min-w-44">
          <Search aria-hidden /> {submitLabel}
        </Button>
      </div>

      <div
        id={id("advanced")}
        hidden={!advanced}
        className="mt-4 grid gap-4 border-t border-border pt-4 sm:grid-cols-2 lg:grid-cols-4"
      >
        <Field id={id("stops")} label="Stops">
          {(a) => (
            <select {...a} {...register("maxStops")} className={selectClass}>
              <option value="any">Any number</option>
              <option value="0">Nonstop only</option>
              <option value="1">Up to 1 stop</option>
              <option value="2">Up to 2 stops</option>
            </select>
          )}
        </Field>
        <Field
          id={id("hours")}
          label="Max journey time (hours)"
          hint="Per direction"
          error={errors.maxHours?.message}
        >
          {(a) => <Input {...a} inputMode="numeric" placeholder="Any" {...register("maxHours")} />}
        </Field>
        <Field id={id("window")} label="Departure time">
          {(a) => (
            <select {...a} {...register("departWindow")} className={selectClass}>
              <option value="any">Any time</option>
              {(["morning", "afternoon", "evening"] as const).map((k) => (
                <option key={k} value={k}>
                  {TIME_WINDOWS[k].label}
                </option>
              ))}
            </select>
          )}
        </Field>
        <div className="grid content-start gap-3 pt-1">
          {(
            [
              ["bag", "Checked bag required", "Only fares that confirm a bag"],
              ["nearby", "Include nearby airports", "e.g. LGW with LHR"],
              ...(departWindow !== "any"
                ? ([
                    ["strictTimes", "Only this time window", "Otherwise it's a preference"],
                  ] as const)
                : []),
            ] as const
          ).map(([name, label, hint]) => (
            <Controller
              key={name}
              control={control}
              name={name}
              render={({ field }) => (
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <Label htmlFor={id(name)}>{label}</Label>
                    <p className="text-xs text-muted">{hint}</p>
                  </div>
                  <Switch id={id(name)} checked={!!field.value} onCheckedChange={field.onChange} />
                </div>
              )}
            />
          ))}
        </div>
      </div>
    </form>
  );
}
