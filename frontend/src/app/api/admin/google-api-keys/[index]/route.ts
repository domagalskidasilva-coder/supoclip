import { createTextProxyResponse, fetchBackend } from "@/server/backend-api";

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ index: string }> },
) {
  const { index } = await params;
  const upstream = await fetchBackend(
    `/admin/google-api-keys/${encodeURIComponent(index)}`,
    {
      method: "DELETE",
      cache: "no-store",
    },
  );

  return createTextProxyResponse(upstream);
}
