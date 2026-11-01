import type { Metadata } from "next";
import { Suspense } from "react";

import { SearchPage } from "@/app/search/search-page";
import { ResultsSkeleton } from "@/components/results/results-view";

export const metadata: Metadata = { title: "Search flights" };

export default function Page() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
          <ResultsSkeleton />
        </div>
      }
    >
      <SearchPage />
    </Suspense>
  );
}
