import { NextResponse } from "next/server";

export async function GET() {
  const apiUrl =
    process.env.BACKEND_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000";
  const normalizedApiUrl = apiUrl.replace(/\/$/, "");

  let upstream = await fetch(`${normalizedApiUrl}/fonts`, {
    cache: "no-store",
  });

  if (upstream.status === 404) {
    upstream = await fetch(`${normalizedApiUrl}/api/fonts`, {
      cache: "no-store",
    });
  }

  const responseText = await upstream.text();
  return new NextResponse(responseText, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("content-type") || "application/json",
    },
  });
}
