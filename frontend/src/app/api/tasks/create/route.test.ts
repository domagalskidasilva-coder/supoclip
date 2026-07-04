import { POST } from "./route";

describe("/api/tasks/create", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.unstubAllEnvs();
    vi.stubGlobal("fetch", vi.fn());
  });

  it("proxies task creation to the backend without auth headers", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ task_id: "task-1" }), {
        status: 200,
        headers: { "Content-Type": "application/json", "x-trace-id": "trace-1" },
      }),
    );

    const payload = {
      source: { url: "https://www.youtube.com/watch?v=demo" },
    };

    const response = await POST(
      new Request("http://localhost/api/tasks/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }),
    );

    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/tasks/",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(payload),
        headers: { "Content-Type": "application/json" },
      }),
    );
    expect(response.status).toBe(200);
    expect(response.headers.get("x-trace-id")).toBe("trace-1");
  });
});
