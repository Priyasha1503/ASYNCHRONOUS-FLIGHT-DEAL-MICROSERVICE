"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { AuthShell } from "@/components/site/auth-shell";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { FormAlert } from "@/components/ui/form-alert";
import { ApiError } from "@/lib/api";
import { registerSchema, useRegister, type RegisterInput } from "@/lib/auth";
import { applyServerErrors } from "@/lib/form-errors";

export default function RegisterPage() {
  const router = useRouter();
  const registerMutation = useRegister();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<RegisterInput>({ resolver: zodResolver(registerSchema), mode: "onTouched" });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await registerMutation.mutateAsync(values);
      toast.success("Welcome to SkyScout", { description: "Your account is ready." });
      router.push("/account");
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setError("email", { type: "server", message: "An account with this email already exists" });
        return;
      }
      setFormError(applyServerErrors(e, setError, ["email", "password", "display_name"]));
    }
  });

  return (
    <AuthShell
      title="Create your account"
      subtitle="Save searches, set target prices and manage alerts."
      footer={
        <>
          Already have an account?{" "}
          <Link href="/signin" className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form noValidate onSubmit={onSubmit} className="grid gap-5">
        <FormAlert message={formError} />
        <Field id="display_name" label="Name (optional)" error={errors.display_name?.message}>
          {(a) => <Input {...a} autoComplete="name" {...register("display_name")} />}
        </Field>
        <Field id="email" label="Email" error={errors.email?.message}>
          {(a) => <Input {...a} type="email" autoComplete="email" {...register("email")} />}
        </Field>
        <Field
          id="password"
          label="Password"
          hint="At least 10 characters. A passphrase works well."
          error={errors.password?.message}
        >
          {(a) => (
            <Input {...a} type="password" autoComplete="new-password" {...register("password")} />
          )}
        </Field>
        <Button type="submit" size="lg" loading={registerMutation.isPending}>
          Create account
        </Button>
      </form>
    </AuthShell>
  );
}
