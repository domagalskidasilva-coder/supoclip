import { NextResponse } from "next/server";

export async function POST(request: Request) {
  const formData = await request.formData();
  const apiUrl =
    process.env.BACKEND_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000";
  const normalizedApiUrl = apiUrl.replace(/\/$/, "");

  let upstream = await fetch(`${normalizedApiUrl}/fonts/upload`, {
    method: "POST",
    body: formData,
  });

  if (upstream.status === 404) {
    upstream = await fetch(`${normalizedApiUrl}/api/fonts/upload`, {
      method: "POST",
      body: formData,
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
