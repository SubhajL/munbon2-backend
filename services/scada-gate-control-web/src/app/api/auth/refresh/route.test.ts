import { NextRequest } from "next/server";
import { afterEach, describe, expect, test, vi } from "vitest";
import { POST } from "./route";

afterEach(() => vi.unstubAllGlobals());

describe("POST /api/auth/refresh", () => {
  test("returns 401 and never calls upstream when no refresh cookie is present", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    const req = new NextRequest("http://localhost/api/auth/refresh", {
      method: "POST",
    });
    const res = await POST(req);

    expect(res.status).toBe(401);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  test("ignores a token supplied via query/header/body — only the cookie counts", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    const req = new NextRequest(
      "http://localhost/api/auth/refresh?refreshToken=from-query",
      {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-refresh-token": "from-header",
        },
        body: JSON.stringify({ refreshToken: "from-body" }),
      },
    );
    const res = await POST(req);

    expect(res.status).toBe(401);
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
