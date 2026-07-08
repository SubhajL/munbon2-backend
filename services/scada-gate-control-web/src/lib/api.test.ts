import { describe, expect, test, vi } from "vitest";
import { ApiError, createApiClient, type SiteSummary } from "./api";

const jsonResponse = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

describe("createApiClient.listSites", () => {
  test("GETs /api/sites with the bearer token and parses the body", async () => {
    const sites: SiteSummary[] = [
      {
        id: "waste-way",
        name: "Waste Way",
        connection: "ok",
        markerColor: "green",
        lastUpdated: null,
      },
    ];
    const fetchImpl = vi.fn(async () => jsonResponse(sites));
    const client = createApiClient({
      baseUrl: "http://api",
      token: "tok",
      fetchImpl,
    });

    expect(await client.listSites()).toEqual(sites);
    expect(fetchImpl).toHaveBeenCalledWith("http://api/api/sites", {
      headers: { authorization: "Bearer tok" },
    });
  });

  test("throws ApiError carrying the HTTP status on failure", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({ error: "unauthorized" }, 401),
    );
    const client = createApiClient({ baseUrl: "http://api", fetchImpl });
    await expect(client.listSites()).rejects.toMatchObject({ status: 401 });
    await expect(client.listSites()).rejects.toBeInstanceOf(ApiError);
  });
});

describe("createApiClient.commandLevel", () => {
  test("POSTs the command and returns the structured result (202 accepted)", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({ status: "accepted", pending: true }, 202),
    );
    const client = createApiClient({
      baseUrl: "http://api",
      token: "t",
      fetchImpl,
    });

    expect(await client.commandLevel("waste-way", 2, true)).toEqual({
      status: "accepted",
      pending: true,
    });
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://api/api/gates/waste-way/command-level",
      {
        method: "POST",
        headers: {
          "content-type": "application/json",
          authorization: "Bearer t",
        },
        body: JSON.stringify({ targetValue: 2, confirmed: true }),
      },
    );
  });

  test("returns the rejection body for a 4xx with a structured result", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({ status: "rejected", reason: "data_offline" }, 409),
    );
    const client = createApiClient({ baseUrl: "http://api", fetchImpl });
    expect(await client.commandLevel("waste-way", 2, true)).toEqual({
      status: "rejected",
      reason: "data_offline",
    });
  });
});

describe("createApiClient auth handling", () => {
  test("prefers a dynamic getToken over the static token for the Authorization header", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse([]));
    const client = createApiClient({
      baseUrl: "http://api",
      token: "static",
      getToken: () => "dynamic",
      fetchImpl,
    });

    await client.listSites();
    expect(fetchImpl).toHaveBeenCalledWith("http://api/api/sites", {
      headers: { authorization: "Bearer dynamic" },
    });
  });

  test("refreshes once on a 401 and retries the request with the new token", async () => {
    const sites: SiteSummary[] = [
      {
        id: "waste-way",
        name: "Waste Way",
        connection: "ok",
        markerColor: "green",
        lastUpdated: null,
      },
    ];
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ error: "unauthorized" }, 401))
      .mockResolvedValueOnce(jsonResponse(sites));
    const onUnauthorized = vi.fn(async () => "fresh");
    const client = createApiClient({
      baseUrl: "http://api",
      getToken: () => "stale",
      onUnauthorized,
      fetchImpl,
    });

    expect(await client.listSites()).toEqual(sites);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    expect(fetchImpl).toHaveBeenLastCalledWith("http://api/api/sites", {
      headers: { authorization: "Bearer fresh" },
    });
  });

  test("surfaces the 401 (no retry) when the refresh yields no token", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({ error: "unauthorized" }, 401),
    );
    const onUnauthorized = vi.fn(async () => null);
    const client = createApiClient({
      baseUrl: "http://api",
      getToken: () => "stale",
      onUnauthorized,
      fetchImpl,
    });

    await expect(client.listSites()).rejects.toMatchObject({ status: 401 });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
});
