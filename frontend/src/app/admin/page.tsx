import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function AdminPage() {
  return (
    <main className="min-h-screen bg-stone-50">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="font-[var(--font-syne)] text-3xl font-bold text-stone-950">
          Local administration
        </h1>
        <p className="mt-3 text-sm text-stone-600">
          User administration was removed. Runtime provider settings now live in
          the global settings page.
        </p>
        <div className="mt-8 flex gap-3">
          <Link href="/settings">
            <Button>Open Settings</Button>
          </Link>
          <Link href="/list">
            <Button variant="outline">View Generations</Button>
          </Link>
        </div>
      </div>
    </main>
  );
}
