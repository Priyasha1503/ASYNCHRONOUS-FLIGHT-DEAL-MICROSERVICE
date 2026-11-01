"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { AuthShell } from "@/components/site/auth-shell";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { FormAlert } from "@/components/ui/form-alert";
import { loginSchema, useLogin, type LoginInput } from "@/lib/auth";
import { applyServerErrors, safeNext } from "@/lib/form-errors";

export function SignInForm() {
  const router = useRouter();
  const params = useSearchParams();
  const login = useLogin();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<LoginInput>({ resolver: zodResolver(loginSchema), mode: "onTouched" });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await login.mutateAsync(values);
      router.push(safeNext(params.get("next")));
    } catch (e) {
      setFormError(applyServerErrors(e, setError, ["email", "password"]));
    }
  });

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to your saved trips and alerts."
      footer={
        <>
          New to SkyScout?{" "}
          <Link href="/register" className="font-medium text-primary hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <form noValidate onSubmit={onSubmit} className="grid gap-5">
        <FormAlert message={formError} />
        <Field id="email" label="Email" error={errors.email?.message}>
          {(a) => <Input {...a} type="email" autoComplete="email" {...register("email")} />}
        </Field>
        <Field id="password" label="Password" error={errors.password?.message}>
          {(a) => (
            <Input
              {...a}
              type="password"
              autoComplete="current-password"
              {...register("password")}
            />
          )}
        </Field>
        <Button type="submit" size="lg" loading={login.isPending}>
          Sign in
        </Button>
      </form>
    </AuthShell>
  );
}
