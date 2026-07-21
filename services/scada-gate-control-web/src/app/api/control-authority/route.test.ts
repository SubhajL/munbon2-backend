import { NextRequest } from "next/server";
import { afterEach, describe, expect, test, vi } from "vitest";
import { GET, POST } from "./route";

const PLAN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

afterEach(() => vi.unstubAllGlobals());

describe("/api/control-authority", () => {
  test("GET rejects a missing bearer before any upstream call", async () => {
    const fetchImpl = vi.fn();
    vi.stubGlobal("fetch", fetchImpl);
    const request = new NextRequest(
      `http://localhost/api/control-authority?planId=${PLAN_ID}&planVersion=3`,
    );

    const response = await GET(request);

    expect(response.status).toBe(401);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  test("POST rejects non-allowlisted actions before any upstream call", async () => {
    const fetchImpl = vi.fn();
    vi.stubGlobal("fetch", fetchImpl);
    const request = new NextRequest("http://localhost/api/control-authority", {
      method: "POST",
      headers: {
        authorization: "Bearer operator-token",
        "content-type": "application/json",
        "x-operator-confirmation": "EXECUTE",
      },
      body: JSON.stringify({
        action: "execute",
        planId: PLAN_ID,
        planVersion: 3,
        reason: "no",
      }),
    });

    const response = await POST(request);

    expect(response.status).toBe(400);
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  test("POST forwards a hold through the fixed Scheduler path", async () => {
    const fetchImpl = vi.fn(async () =>
      Response.json({ plan_id: PLAN_ID, plan_version: 3, status: "held" }),
    ) as unknown as typeof fetch;
    vi.stubGlobal("fetch", fetchImpl);
    const request = new NextRequest("http://localhost/api/control-authority", {
      method: "POST",
      headers: {
        authorization: "Bearer operator-token",
        "content-type": "application/json",
        "x-operator-confirmation": `HOLD ${PLAN_ID} v3`,
      },
      body: JSON.stringify({
        action: "hold",
        planId: PLAN_ID,
        planVersion: 3,
        reason: "safety stop",
      }),
    });

    const response = await POST(request);

    expect(response.status).toBe(200);
    expect(fetchImpl).toHaveBeenCalledWith(
      `http://localhost:3021/api/v1/control-plans/${PLAN_ID}/versions/3/hold`,
      expect.objectContaining({ method: "POST", cache: "no-store" }),
    );
  });
});
