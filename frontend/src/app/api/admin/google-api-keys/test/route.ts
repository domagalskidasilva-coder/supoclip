import { createTextProxyResponse, fetchBackend } from "@/server/backend-api";

export async function POST(request: Request) {
  const body = await request.text();
  const upstream = await fetchBackend("/admin/google-api-keys/test", {
    method: "POST",
    extraHeaders: { "Content-Type": "application/json" },
    body,
    cache: "no-store",
  });

  return createTextProxyResponse(upstream);
}
