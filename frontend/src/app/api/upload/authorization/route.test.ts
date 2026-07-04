import { POST } from "./route";

describe("/api/upload/authorization", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.unstubAllEnvs();
  });

  it("returns direct upload details without auth headers", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.supoclip.com/");

    const response = await POST();

    expect(response.status).toBe(200);
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    await expect(response.json()).resolves.toEqual({
      directUpload: true,
      uploadUrl: "https://api.supoclip.com/upload",
      headers: {},
    });
  });
});
