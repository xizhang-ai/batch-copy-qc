import { ApiError, apiRequest } from "./client";

describe("apiRequest", () => {
  afterEach(() => vi.restoreAllMocks());

  it("rejects absolute and protocol-relative URLs", async () => {
    await expect(apiRequest("https://example.com/api")).rejects.toMatchObject({ code: "API_URL_REJECTED" });
    await expect(apiRequest("//example.com/api")).rejects.toMatchObject({ code: "API_URL_REJECTED" });
  });

  it("normalizes backend error payloads", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: "RULE_CONFLICT", message: "规则冲突" } }), { status: 409 })));
    await expect(apiRequest("/api/test")).rejects.toEqual(expect.objectContaining({ code: "RULE_CONFLICT", status: 409 }));
  });

  it("maps invalid JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("not-json", { status: 200 })));
    await expect(apiRequest("/api/test")).rejects.toBeInstanceOf(ApiError);
    await expect(apiRequest("/api/test")).rejects.toMatchObject({ code: "API_RESPONSE_INVALID" });
  });
});
