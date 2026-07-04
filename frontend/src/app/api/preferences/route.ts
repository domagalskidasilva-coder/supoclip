import { NextRequest, NextResponse } from "next/server";

const DEFAULT_PREFERENCES = {
  fontFamily: "THEBOLDFONT",
  fontSize: 24,
  fontColor: "#FFFFFF",
  notifyOnCompletion: false,
};

export async function GET() {
  return NextResponse.json(DEFAULT_PREFERENCES);
}

export async function PATCH(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  const fontFamily =
    typeof body.fontFamily === "string" && body.fontFamily.trim()
      ? body.fontFamily.trim()
      : DEFAULT_PREFERENCES.fontFamily;
  const fontSize =
    typeof body.fontSize === "number"
      ? Math.max(12, Math.min(72, Math.round(body.fontSize)))
      : DEFAULT_PREFERENCES.fontSize;
  const fontColor =
    typeof body.fontColor === "string" && /^#[0-9A-Fa-f]{6}$/.test(body.fontColor)
      ? body.fontColor.toUpperCase()
      : DEFAULT_PREFERENCES.fontColor;

  return NextResponse.json({
    fontFamily,
    fontSize,
    fontColor,
    notifyOnCompletion: false,
  });
}
