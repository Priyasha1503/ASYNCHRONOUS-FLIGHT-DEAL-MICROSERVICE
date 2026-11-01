import * as LabelPrimitive from "@radix-ui/react-label";
import { AlertCircle } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

export function Label({ className, ...props }: React.ComponentProps<typeof LabelPrimitive.Root>) {
  return (
    <LabelPrimitive.Root
      className={cn("text-sm font-medium text-text select-none", className)}
      {...props}
    />
  );
}

export function Input({ className, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      className={cn(
        "h-10 w-full rounded-md border border-border-strong bg-surface px-3 text-sm text-text",
        "shadow-sm transition-[border-color,box-shadow] duration-[var(--dur-fast)] outline-none",
        "placeholder:text-subtle",
        "focus-visible:border-primary focus-visible:ring-3 focus-visible:ring-primary/20 focus-visible:outline-none",
        "aria-invalid:border-danger aria-invalid:focus-visible:ring-danger/20",
        "disabled:cursor-not-allowed disabled:opacity-60",
        className,
      )}
      {...props}
    />
  );
}

type FieldProps = {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  children: (aria: {
    id: string;
    "aria-invalid": boolean | undefined;
    "aria-describedby": string | undefined;
  }) => React.ReactNode;
  className?: string;
};

/** Label + control + hint/error, wired for screen readers. */
export function Field({ id, label, hint, error, children, className }: FieldProps) {
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  return (
    <div className={cn("grid content-start gap-1.5", className)}>
      <Label htmlFor={id}>{label}</Label>
      {children({
        id,
        "aria-invalid": error ? true : undefined,
        "aria-describedby": [errorId, hintId].filter(Boolean).join(" ") || undefined,
      })}
      {error ? (
        <p id={errorId} className="flex items-center gap-1.5 text-sm text-danger" role="alert">
          <AlertCircle className="size-3.5 shrink-0" aria-hidden />
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="text-sm text-muted">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export function Switch({
  checked,
  onCheckedChange,
  id,
  ...props
}: {
  checked: boolean;
  onCheckedChange: (v: boolean) => void;
  id: string;
} & Omit<React.ComponentProps<"button">, "onChange">) {
  return (
    <button
      type="button"
      role="switch"
      id={id}
      aria-checked={checked}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition-colors",
        "duration-[var(--dur-base)]",
        checked ? "border-primary bg-primary" : "border-border-strong bg-surface-sunken",
      )}
      {...props}
    >
      <span
        aria-hidden
        className={cn(
          "inline-block size-4.5 rounded-full bg-white shadow-sm transition-transform duration-[var(--dur-base)] ease-out",
          checked ? "translate-x-5.5" : "translate-x-0.5",
        )}
      />
    </button>
  );
}
