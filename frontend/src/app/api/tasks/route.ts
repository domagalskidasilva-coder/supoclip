import { createProxyResponse, fetchBackend } from "@/server/backend-api";

export async function GET() {
  const upstream = await fetchBackend("/tasks/", {
    method: "GET",
    cache: "no-store",
  });

  return createProxyResponse(upstream);
}
