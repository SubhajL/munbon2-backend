import { NextRequest } from "next/server";
import { describe, expect, test } from "vitest";
import { readRefreshCookie, toNextResponse } from "./auth-route";

describe("readRefreshCookie", () => {
  test("reads the sgc_refresh cookie value from the request", () => {
    const req = new NextRequest("http://localhost/api/auth/refresh", {
      headers: { cookie: "sgc_refresh=rtk-123" },
    });
    expect(readRefreshCookie(req)).toBe("rtk-123");
  });

  test("returns undefined when the cookie is absent", () => {
    const req = new NextRequest("http://localhost/api/auth/refresh");
    expect(readRefreshCookie(req)).toBeUndefined();
  });
});

describe("toNextResponse", () => {
  test("sets a hardened, httpOnly, same-origin refresh cookie when present", () => {
    const res = toNextResponse({
      status: 200,
      body: { ok: true },
      setRefreshCookie: "rtk",
    });

    expect(res.status).toBe(200);
    const setCookie = res.headers.get("set-cookie") ?? "";
    expect(setCookie).toContain("sgc_refresh=rtk");
    expect(setCookie).toContain("HttpOnly");
    expect(setCookie).toContain("Path=/api/auth");
    expect(setCookie.toLowerCase()).toContain("samesite=lax");
  });

  test("expires the cookie when clearing the session", () => {
    const res = toNextResponse({
      status: 200,
      body: { ok: true },
      clearRefreshCookie: true,
    });
    expect(res.headers.get("set-cookie") ?? "").toContain("Max-Age=0");
  });

  test("passes the upstream body and status through untouched", async () => {
    const res = toNextResponse({
      status: 401,
      body: { error: "No active session" },
    });
    expect(res.status).toBe(401);
    expect(await res.json()).toEqual({ error: "No active session" });
  });
});
