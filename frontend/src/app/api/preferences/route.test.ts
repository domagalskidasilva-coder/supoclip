import { GET, PATCH } from "./route";

describe("/api/preferences", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("returns local default preferences without a session", async () => {
    const response = await GET();

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      fontFamily: "THEBOLDFONT",
      fontSize: 24,
      fontColor: "#FFFFFF",
      notifyOnCompletion: false,
    });
  });

  it("normalizes PATCH payloads for local preferences", async () => {
    const response = await PATCH(
      new Request("http://localhost/api/preferences", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fontFamily: " Inter ",
          fontSize: 100,
          fontColor: "#123abc",
          notifyOnCompletion: true,
        }),
      }) as never,
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      fontFamily: "Inter",
      fontSize: 72,
      fontColor: "#123ABC",
      notifyOnCompletion: false,
    });
  });
});
