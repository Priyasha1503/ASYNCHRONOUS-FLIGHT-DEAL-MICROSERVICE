"use client";

import Link from "next/link";
import { useEffect } from "react";
import { toast } from "sonner";

import { SearchForm } from "@/components/search/search-form";
import { useMe } from "@/lib/auth";
import { defaultSearch } from "@/lib/search";

/** Hero search. Defaults follow the signed-in user's currency and home airport. */
export function HeroSearch() {
  const { data: me } = useMe();

  // Confirmation after account deletion (which ends with a full page load to /?account=deleted).
  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.get("account") === "deleted") {
      toast("Your account has been deleted");
      url.searchParams.delete("account");
      window.history.replaceState(null, "", url.pathname + url.search + url.hash);
    }
  }, []);

  return (
    <div className="grid gap-3">
      <SearchForm
        defaultValues={defaultSearch(me?.preferences.currency, me?.preferences.home_airport ?? "")}
      />
      {me === null && (
        <p className="text-sm text-white/80">
          Searching is free.{" "}
          <Link href="/register" className="font-medium text-white underline underline-offset-4">
            Create an account
          </Link>{" "}
          to save searches and get price alerts.
        </p>
      )}
    </div>
  );
}
