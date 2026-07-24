import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { describe, expect, test, vi } from "vitest";
import {
  ReadOnlyGateStatusError,
  createReadOnlyGateStatusClient,
} from "./read-only-gate-status";
import type { GateStatus } from "./api";

const gateStatus: GateStatus = {
  id: "gate 7/ฝาย",
  name: "Gate Seven",
  endpoint: { host: "127.0.0.1", port: 502, unitId: 7 },
  connection: "ok",
  markerColor: "green",
  lastUpdated: "2026-07-24T00:00:00Z",
  lastError: null,
  gateLevel: {
    raw: 2,
    value: {
      level: 2,
      thaiLabel: "ระดับ 2",
      technicalLabel: "Level 2",
      flowRate: 1.5,
    },
    quality: "ok",
    lastUpdated: "2026-07-24T00:00:00Z",
    lastError: null,
  },
  doorSw: {
    raw: 1,
    value: { closed: true, thaiLabel: "ปิด" },
    quality: "ok",
    lastUpdated: "2026-07-24T00:00:00Z",
    lastError: null,
  },
  horn: {
    raw: 0,
    value: { on: false, thaiLabel: "ปิด" },
    quality: "ok",
    lastUpdated: "2026-07-24T00:00:00Z",
    lastError: null,
  },
  gateCf: {
    raw: 1,
    value: { confirmed: true },
    quality: "ok",
    lastUpdated: "2026-07-24T00:00:00Z",
    lastError: null,
  },
};

const jsonResponse = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

describe("createReadOnlyGateStatusClient", () => {
  test("fetches only the exact encoded gate-status path with bearer auth", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(gateStatus));
    const client = createReadOnlyGateStatusClient({
      getToken: () => "viewer-token",
      fetchImpl,
    });

    await expect(client.getGateStatus("gate 7/ฝาย")).resolves.toEqual(
      gateStatus,
    );
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/read-only/gates/gate%207%2F%E0%B8%9D%E0%B8%B2%E0%B8%A2/status",
      {
        method: "GET",
        cache: "no-store",
        headers: { authorization: "Bearer viewer-token" },
      },
    );
  });

  test("retries the same GET once with the refreshed bearer after a 401", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ error: "unauthorized" }, 401))
      .mockResolvedValueOnce(jsonResponse({ ...gateStatus, id: "gate-7" }));
    const onUnauthorized = vi.fn(async () => "fresh-token");
    const client = createReadOnlyGateStatusClient({
      getToken: () => "expired-token",
      onUnauthorized,
      fetchImpl,
    });

    await expect(client.getGateStatus("gate-7")).resolves.toEqual({
      ...gateStatus,
      id: "gate-7",
    });
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "/api/read-only/gates/gate-7/status",
      {
        method: "GET",
        cache: "no-store",
        headers: { authorization: "Bearer expired-token" },
      },
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "/api/read-only/gates/gate-7/status",
      {
        method: "GET",
        cache: "no-store",
        headers: { authorization: "Bearer fresh-token" },
      },
    );
  });

  test("fails closed when refresh yields no bearer", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({ error: "unauthorized" }, 401),
    );
    const client = createReadOnlyGateStatusClient({
      getToken: () => "expired-token",
      onUnauthorized: vi.fn(async () => null),
      fetchImpl,
    });

    await expect(client.getGateStatus("gate-7")).rejects.toBeInstanceOf(
      ReadOnlyGateStatusError,
    );
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  test("fails closed without making a request when the initial bearer is absent", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(gateStatus));
    const client = createReadOnlyGateStatusClient({
      getToken: () => undefined,
      fetchImpl,
    });

    await expect(client.getGateStatus("gate-7")).rejects.toMatchObject({
      status: 401,
    });
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  test("rejects a malformed successful response as unavailable upstream data", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({ id: "gate-7", name: "incomplete" }),
    );
    const client = createReadOnlyGateStatusClient({
      getToken: () => "viewer-token",
      fetchImpl,
    });

    await expect(client.getGateStatus("gate-7")).rejects.toMatchObject({
      status: 502,
    });
  });

  test("rejects a valid status document for a different gate ID", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({ ...gateStatus, id: "another-gate" }),
    );
    const client = createReadOnlyGateStatusClient({
      getToken: () => "viewer-token",
      fetchImpl,
    });

    await expect(client.getGateStatus("gate 7/ฝาย")).rejects.toMatchObject({
      status: 502,
    });
  });

  test("has an allowlisted type-only dependency and no mutation vocabulary", async () => {
    const source = await readFile(
      resolve(process.cwd(), "src/lib/read-only-gate-status.ts"),
      "utf8",
    );
    const importSources = Array.from(
      source.matchAll(/from\s+["']([^"']+)["']/g),
      (match) => match[1],
    );

    expect(importSources).toEqual(["./api"]);
    expect(source).not.toMatch(
      /createApiClient|commandLevel|commandHorn|method:\s*["'](?:POST|PUT|PATCH|DELETE)["']/,
    );
  });
});
