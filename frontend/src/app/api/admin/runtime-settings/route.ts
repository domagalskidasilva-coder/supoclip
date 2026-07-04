import { createTextProxyResponse, fetchBackend } from "@/server/backend-api";

export async function GET() {
  const upstream = await fetchBackend("/admin/runtime-settings", {
    method: "GET",
    cache: "no-store",
  });

  return createTextProxyResponse(upstream);
}

export async function PATCH(request: Request) {
  const body = await request.text();
  const upstream = await fetchBackend("/admin/runtime-settings", {
    method: "PATCH",
    extraHeaders: { "Content-Type": "application/json" },
    body,
    cache: "no-store",
  });

  return createTextProxyResponse(upstream);
}
