import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="mx-auto grid max-w-xl justify-items-start gap-4 px-4 py-24 sm:px-6">
      <p className="text-sm font-semibold tracking-wide text-accent-text uppercase">404</p>
      <h1 className="font-display text-4xl font-semibold tracking-tight">Off the flight path</h1>
      <p className="text-muted">The page you were looking for doesn&apos;t exist or has moved.</p>
      <Button asChild className="mt-2">
        <Link href="/">Back to SkyScout</Link>
      </Button>
    </div>
  );
}
