import { NextRequest } from "next/server";
import { afterEach, describe, expect, test, vi } from "vitest";
import { POST } from "./route";

afterEach(() => vi.unstubAllGlobals());

describe("POST /api/auth/logout", () => {
  test("clears the cookie without calling upstream when there is no session cookie", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    // A token in the body must be ignored — only the cookie is honoured.
    const req = new NextRequest("http://localhost/api/auth/logout", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ refreshToken: "from-body" }),
    });
    const res = await POST(req);

    expect(res.status).toBe(200);
    expect(res.headers.get("set-cookie") ?? "").toContain("Max-Age=0");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  test("revokes upstream and clears the cookie when the session cookie is present", async () => {
    const fetchSpy = vi.fn(
      async () =>
        new Response(JSON.stringify({ success: true }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchSpy);

    const req = new NextRequest("http://localhost/api/auth/logout", {
      method: "POST",
      headers: { cookie: "sgc_refresh=rtk" },
    });
    const res = await POST(req);

    expect(res.status).toBe(200);
    expect(res.headers.get("set-cookie") ?? "").toContain("Max-Age=0");
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });
});
