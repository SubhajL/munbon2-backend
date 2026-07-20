import { describe, expect, test, vi } from "vitest";
import { ControlPlanApiError, createControlPlansClient } from "./control-plans-api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("createControlPlansClient", () => {
  test("test_control_plane_reads_are_not_cached: every read is cache: no-store", async () => {
    const inits: RequestInit[] = [];
    const fetchImpl = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      inits.push(init ?? {});
      return jsonResponse({ plan_id: "p", plan_version: 1, intents: [] });
    }) as unknown as typeof fetch;
    const client = createControlPlansClient({ baseUrl: "http://bff", fetchImpl });

    await client.getIntentTimeline("p", 1);
    await client.listControlPlans();

    expect(inits).toHaveLength(2);
    for (const init of inits) expect(init.cache).toBe("no-store");
  });

  test("forwards the operator bearer and builds the exact bounded path", async () => {
    const captured: { url: string; init: RequestInit }[] = [];
    const fetchImpl = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      captured.push({ url: String(url), init: init ?? {} });
      return jsonResponse({ plan_id: "p", plan_version: 2, observations: [] });
    }) as unknown as typeof fetch;
    const client = createControlPlansClient({
      baseUrl: "http://bff",
      fetchImpl,
      getToken: () => "op-token",
    });

    await client.getReadbackObservations("p", 2);

    expect(captured[0].url).toBe(
      "http://bff/api/v1/control-plans/p/versions/2/readback-observations",
    );
    expect((captured[0].init.headers as Record<string, string>).authorization).toBe(
      "Bearer op-token",
    );
  });

  test("a non-200 raises ControlPlanApiError — never a silent empty/success", async () => {
    const fetchImpl = vi.fn(async () => new Response("nope", { status: 503 })) as unknown as typeof fetch;
    const client = createControlPlansClient({ baseUrl: "http://bff", fetchImpl });
    await expect(client.getExecutionState("p", 1)).rejects.toBeInstanceOf(ControlPlanApiError);
  });

  test("the client exposes ONLY read methods — no write/command/actuate affordance", () => {
    const client = createControlPlansClient({ baseUrl: "http://bff" });
    expect(Object.keys(client).sort()).toEqual([
      "getExecutionState",
      "getIntentTimeline",
      "getLifecycleHistory",
      "getPredictionCoverage",
      "getReadbackObservations",
      "listControlPlans",
    ]);
    for (const name of Object.keys(client)) {
      expect(name).not.toMatch(/post|put|patch|delete|command|write|actuate|create|update|approve|activate|cancel|hold|resume/i);
    }
  });

  test("a 401 refreshes the token once and retries — a long-open dashboard survives expiry", async () => {
    let call = 0;
    const seenTokens: (string | null)[] = [];
    const fetchImpl = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      call += 1;
      seenTokens.push((init?.headers as Record<string, string>)?.authorization ?? null);
      if (call === 1) return new Response("unauthorized", { status: 401 });
      return jsonResponse({ plan_id: "p", plan_version: 1, is_held: false, hold_events: [] });
    }) as unknown as typeof fetch;
    const client = createControlPlansClient({
      baseUrl: "http://bff",
      fetchImpl,
      getToken: () => "expired",
      onUnauthorized: async () => "fresh",
    });
    const result = await client.getExecutionState("p", 1);
    expect(result).toMatchObject({ is_held: false });
    expect(seenTokens).toEqual(["Bearer expired", "Bearer fresh"]);
  });
});
