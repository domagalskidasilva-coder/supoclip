import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function SignUpPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-white px-4">
      <div className="max-w-md text-center">
        <h1 className="text-2xl font-semibold text-stone-950">Accounts removed</h1>
        <p className="mt-3 text-sm text-stone-600">
          SupoClip now runs as a local app without sign-up.
        </p>
        <Link href="/" className="mt-6 inline-block">
          <Button>Open app</Button>
        </Link>
      </div>
    </main>
  );
}
