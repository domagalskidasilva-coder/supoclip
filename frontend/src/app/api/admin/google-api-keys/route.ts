import { createTextProxyResponse, fetchBackend } from "@/server/backend-api";

export async function GET() {
  const upstream = await fetchBackend("/admin/google-api-keys", {
    method: "GET",
    cache: "no-store",
  });

  return createTextProxyResponse(upstream);
}

export async function POST(request: Request) {
  const body = await request.text();
  const upstream = await fetchBackend("/admin/google-api-keys", {
    method: "POST",
    extraHeaders: { "Content-Type": "application/json" },
    body,
    cache: "no-store",
  });

  return createTextProxyResponse(upstream);
}
