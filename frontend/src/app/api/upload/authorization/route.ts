import { NextResponse } from "next/server";

export async function POST() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const normalizedApiUrl = apiUrl.replace(/\/$/, "");

  return NextResponse.json(
    {
      directUpload: true,
      uploadUrl: `${normalizedApiUrl}/upload`,
      headers: {},
    },
    {
      headers: {
        "Cache-Control": "no-store",
      },
    },
  );
}
