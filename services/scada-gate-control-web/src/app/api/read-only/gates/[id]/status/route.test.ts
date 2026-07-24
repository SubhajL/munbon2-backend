import { NextRequest } from "next/server";
import { afterEach, describe, expect, test, vi } from "vitest";
import * as routeModule from "./route";

const { GET } = routeModule;

const gateStatus = {
  id: "gate 7/ฝาย",
  name: "Gate Seven",
  endpoint: { host: "127.0.0.1", port: 502, unitId: 7 },
  connection: "offline",
  markerColor: "red",
  lastUpdated: null,
  lastError: "connection refused",
  gateLevel: {
    raw: null,
    value: null,
    quality: "offline",
    lastUpdated: null,
    lastError: "connection refused",
  },
  doorSw: {
    raw: null,
    value: null,
    quality: "offline",
    lastUpdated: null,
    lastError: "connection refused",
  },
  horn: {
    raw: null,
    value: null,
    quality: "offline",
    lastUpdated: null,
    lastError: "connection refused",
  },
  gateCf: {
    raw: null,
    value: null,
    quality: "offline",
    lastUpdated: null,
    lastError: "connection refused",
  },
};

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("GET /api/read-only/gates/[id]/status", () => {
  test("exports GET only and has no mutation handler", () => {
    expect(Object.keys(routeModule)).toEqual(["GET"]);
  });

  test("proxies only the exact encoded SCADA status GET with bearer auth", async () => {
    const fetchImpl = vi.fn(async () => Response.json(gateStatus));
    vi.stubGlobal("fetch", fetchImpl);
    const request = new NextRequest(
      "http://localhost/api/read-only/gates/gate%207%2F%E0%B8%9D%E0%B8%B2%E0%B8%A2/status",
      { headers: { authorization: "Bearer viewer-token" } },
    );

    const response = await GET(request, {
      params: Promise.resolve({ id: "gate 7/ฝาย" }),
    });

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual(gateStatus);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://localhost:3030/api/gates/gate%207%2F%E0%B8%9D%E0%B8%B2%E0%B8%A2/status",
      expect.objectContaining({
        method: "GET",
        cache: "no-store",
        redirect: "error",
        headers: { authorization: "Bearer viewer-token" },
      }),
    );
  });

  test("rejects a missing bearer before any upstream request", async () => {
    const fetchImpl = vi.fn();
    vi.stubGlobal("fetch", fetchImpl);
    const request = new NextRequest(
      "http://localhost/api/read-only/gates/waste-way/status",
    );

    const response = await GET(request, {
      params: Promise.resolve({ id: "waste-way" }),
    });

    expect(response.status).toBe(401);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  test.each([401, 404])(
    "passes through an upstream %s without caching",
    async (status) => {
      vi.stubGlobal(
        "fetch",
        vi.fn(async () =>
          Response.json({ error: "upstream rejection" }, { status }),
        ),
      );
      const request = new NextRequest(
        "http://localhost/api/read-only/gates/waste-way/status",
        { headers: { authorization: "Bearer viewer-token" } },
      );

      const response = await GET(request, {
        params: Promise.resolve({ id: "waste-way" }),
      });

      expect(response.status).toBe(status);
      expect(response.headers.get("cache-control")).toBe("no-store");
      await expect(response.json()).resolves.toEqual({
        error: "upstream rejection",
      });
    },
  );

  test("fails closed before fetch when the server-only SCADA URL is malformed", async () => {
    vi.stubEnv(
      "SCADA_GATE_CONTROL_URL",
      "https://operator:secret@scada.example/api?unsafe=true",
    );
    const fetchImpl = vi.fn();
    vi.stubGlobal("fetch", fetchImpl);
    const request = new NextRequest(
      "http://localhost/api/read-only/gates/waste-way/status",
      { headers: { authorization: "Bearer viewer-token" } },
    );

    const response = await GET(request, {
      params: Promise.resolve({ id: "waste-way" }),
    });

    expect(response.status).toBe(503);
    expect(response.headers.get("cache-control")).toBe("no-store");
    await expect(response.json()).resolves.toEqual({
      error: "Gate status service is unavailable",
    });
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  test("fails closed with no-store when SCADA is unavailable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("connection refused");
      }),
    );
    const request = new NextRequest(
      "http://localhost/api/read-only/gates/waste-way/status",
      { headers: { authorization: "Bearer viewer-token" } },
    );

    const response = await GET(request, {
      params: Promise.resolve({ id: "waste-way" }),
    });

    expect(response.status).toBe(503);
    expect(response.headers.get("cache-control")).toBe("no-store");
    await expect(response.json()).resolves.toEqual({
      error: "Gate status service is unavailable",
    });
  });
});
