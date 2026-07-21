import { describe, expect, test, vi } from "vitest";
import {
  ControlAuthorityProxyError,
  mutateControlAuthority,
  readControlAuthority,
} from "./control-authority-proxy";

const PLAN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const GRANT_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const SHA_A = "a".repeat(64);
const SHA_B = "b".repeat(64);
const SHA_C = "c".repeat(64);

const applicability = {
  plan_id: PLAN_ID,
  plan_version: 3,
  evaluated_at: "2026-07-21T02:00:00Z",
  lifecycle_state: "shadow_active",
  model_release_id: "model-r1",
  model_release_content_hash: SHA_A,
  engine_descriptor_content_hash: SHA_B,
  model_release_commandable: true,
  capability_release_id: "cap-r1",
  capability_hash: SHA_C,
  capability_configured: true,
  capability_matches_outbox: true,
  scope: {
    schema_version: 1,
    gate_paths: [
      {
        section_id: "S1",
        canonical_gate_id: "G1",
        path_reach_ids: ["R1"],
      },
    ],
  },
  flow_lower_exclusive_m3s: 0,
  flow_upper_inclusive_m3s: 5,
  initialization: { kind: "dry" },
  maximum_continuous_open_seconds: 3600,
  maximum_intermediate_trims: 1,
  outbox_intent_count: 2,
  accepted_receipt_intent_count: 2,
  matching_receipt_intent_count: 2,
  receipt_coverage_complete: true,
  existing_grant_status: null,
  existing_grant_id: null,
  blockers: [],
  can_grant: true,
};

const grant = {
  grant_id: GRANT_ID,
  plan_id: PLAN_ID,
  plan_version: 3,
  status: "active",
  effective_expires_at: "2026-07-21T12:00:00Z",
  model_release_id: "model-r1",
  model_release_content_hash: SHA_A,
  engine_descriptor_content_hash: SHA_B,
  capability_release_id: "cap-r1",
  capability_hash: SHA_C,
  grant_content_sha256: "d".repeat(64),
  events: [
    {
      event_sequence: 1,
      event_type: "granted",
      effective_expires_at: "2026-07-21T12:00:00Z",
      actor_subject: "admin-1",
      reason: "pilot",
      occurred_at: "2026-07-21T02:00:00Z",
    },
  ],
};

const deps = (fetchImpl: typeof fetch) => ({
  schedulerBaseUrl: "http://scheduler:3021",
  scadaBaseUrl: "http://scada:3030",
  fetchImpl,
});

function json(body: unknown, status = 200): Response {
  return Response.json(body, { status });
}

describe("readControlAuthority", () => {
  test("reads fixed Scheduler and SCADA paths and treats absent grant as null", async () => {
    const seen: string[] = [];
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      seen.push(url);
      if (url.includes("applicability")) return json(applicability);
      if (url.includes("authority-grants?")) return json({ detail: "none" }, 404);
      if (url.endsWith("/health")) {
        return json({ status: "healthy", service: "scada-gate-control" });
      }
      return json({
        schema_version: 1,
        capability_release_id: "cap-r1",
        capability_hash: SHA_C,
        capabilities: {},
      });
    }) as unknown as typeof fetch;

    const result = await readControlAuthority(
      { planId: PLAN_ID, planVersion: 3, accessToken: "operator-token" },
      deps(fetchImpl),
    );

    expect(result.grant).toBeNull();
    expect(result.scada).toEqual({
      available: true,
      healthy: true,
      capability_release_id: "cap-r1",
      capability_hash: SHA_C,
      matches_scheduler: true,
    });
    expect(seen.sort()).toEqual(
      [
        `http://scheduler:3021/api/v1/authority-grants/applicability?plan_id=${PLAN_ID}&plan_version=3`,
        `http://scheduler:3021/api/v1/authority-grants?plan_id=${PLAN_ID}&plan_version=3`,
        "http://scada:3030/health",
        "http://scada:3030/internal/v1/device-capabilities",
      ].sort(),
    );
  });

  test("represents a SCADA outage as fresh unavailable status", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("applicability")) return json(applicability);
      if (url.includes("authority-grants?")) return json({}, 404);
      return json({ error: "down" }, 503);
    }) as unknown as typeof fetch;

    const result = await readControlAuthority(
      { planId: PLAN_ID, planVersion: 3, accessToken: "operator-token" },
      deps(fetchImpl),
    );
    expect(result.scada).toEqual({
      available: false,
      healthy: false,
      capability_release_id: null,
      capability_hash: null,
      matches_scheduler: false,
    });
  });

  test.each([401, 403])(
    "represents SCADA status %s as unavailable without failing Scheduler state",
    async (status) => {
      const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("applicability")) return json(applicability);
        if (url.includes("authority-grants?")) return json({}, 404);
        return json({ error: "denied" }, status);
      }) as unknown as typeof fetch;

      const result = await readControlAuthority(
        { planId: PLAN_ID, planVersion: 3, accessToken: "operator-token" },
        deps(fetchImpl),
      );

      expect(result.scada).toEqual({
        available: false,
        healthy: false,
        capability_release_id: null,
        capability_hash: null,
        matches_scheduler: false,
      });
    },
  );

  test("represents malformed SCADA evidence as unavailable", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("applicability")) return json(applicability);
      if (url.includes("authority-grants?")) return json({}, 404);
      if (url.endsWith("/health")) return json({ status: "maybe" });
      return json({ capability_release_id: 7, capability_hash: "bad" });
    }) as unknown as typeof fetch;

    const result = await readControlAuthority(
      { planId: PLAN_ID, planVersion: 3, accessToken: "operator-token" },
      deps(fetchImpl),
    );

    expect(result.scada.available).toBe(false);
  });

  test("represents malformed SCADA configuration as unavailable", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("applicability")) return json(applicability);
      if (url.includes("authority-grants?")) return json({}, 404);
      throw new Error(`unexpected SCADA request: ${url}`);
    }) as unknown as typeof fetch;

    const result = await readControlAuthority(
      { planId: PLAN_ID, planVersion: 3, accessToken: "operator-token" },
      { ...deps(fetchImpl), scadaBaseUrl: "http://scada:3030/not-host-only" },
    );

    expect(result.scada).toEqual({
      available: false,
      healthy: false,
      capability_release_id: null,
      capability_hash: null,
      matches_scheduler: false,
    });
  });

  test("applies a bounded deadline to every upstream request", async () => {
    const timeout = vi.spyOn(AbortSignal, "timeout");
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("applicability")) return json(applicability);
      if (url.includes("authority-grants?")) return json({}, 404);
      if (url.endsWith("/health")) {
        return json({ status: "healthy", service: "scada-gate-control" });
      }
      return json({ capability_release_id: "cap-r1", capability_hash: SHA_C });
    }) as unknown as typeof fetch;

    await readControlAuthority(
      { planId: PLAN_ID, planVersion: 3, accessToken: "operator-token" },
      deps(fetchImpl),
    );

    expect(timeout).toHaveBeenCalledTimes(4);
    expect(timeout).toHaveBeenCalledWith(5_000);
    timeout.mockRestore();
  });

  test("rejects a grant whose event ledger violates the upstream contract", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("applicability")) {
        return json({
          ...applicability,
          existing_grant_status: "active",
          existing_grant_id: GRANT_ID,
          blockers: ["grant_already_exists"],
          can_grant: false,
        });
      }
      if (url.includes("authority-grants?")) {
        return json({ ...grant, events: [{}] });
      }
      if (url.endsWith("/health")) {
        return json({ status: "healthy", service: "scada-gate-control" });
      }
      return json({
        capability_release_id: "cap-r1",
        capability_hash: SHA_C,
      });
    }) as unknown as typeof fetch;

    await expect(
      readControlAuthority(
        { planId: PLAN_ID, planVersion: 3, accessToken: "operator-token" },
        deps(fetchImpl),
      ),
    ).rejects.toMatchObject({ status: 502 });
  });
});

describe("mutateControlAuthority", () => {
  test("hold uses only its exact Scheduler path and forwards confirmation", async () => {
    const calls: { url: string; init: RequestInit }[] = [];
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(input), init: init ?? {} });
      return json({ plan_id: PLAN_ID, plan_version: 3, status: "held" });
    }) as unknown as typeof fetch;

    await mutateControlAuthority(
      {
        action: "hold",
        planId: PLAN_ID,
        planVersion: 3,
        accessToken: "operator-token",
        confirmation: `HOLD ${PLAN_ID} v3`,
        reason: "safety stop",
      },
      deps(fetchImpl),
    );

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe(
      `http://scheduler:3021/api/v1/control-plans/${PLAN_ID}/versions/3/hold`,
    );
    expect(calls[0].init.method).toBe("POST");
    expect(calls[0].init.headers).toMatchObject({
      authorization: "Bearer operator-token",
      "x-operator-confirmation": `HOLD ${PLAN_ID} v3`,
    });
    expect(calls[0].url).not.toMatch(/command|actuat|gate/i);
  });

  test("hold remains available when the SCADA URL is malformed", async () => {
    const fetchImpl = vi.fn(async () =>
      json({ plan_id: PLAN_ID, plan_version: 3, status: "held" }),
    ) as unknown as typeof fetch;

    await mutateControlAuthority(
      {
        action: "hold",
        planId: PLAN_ID,
        planVersion: 3,
        accessToken: "operator-token",
        confirmation: `HOLD ${PLAN_ID} v3`,
        reason: "safety stop",
      },
      { ...deps(fetchImpl), scadaBaseUrl: "http://scada:3030/machine-path" },
    );

    expect(fetchImpl).toHaveBeenCalledOnce();
  });

  test("revoke verifies the grant directly when applicability is unavailable", async () => {
    const calls: string[] = [];
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      calls.push(url);
      if ((init?.method ?? "GET") === "POST") return json(grant);
      if (url.endsWith(`/authority-grants/${GRANT_ID}`)) return json(grant);
      return json({ error: "applicability broken" }, 503);
    }) as unknown as typeof fetch;

    await mutateControlAuthority(
      {
        action: "revoke",
        planId: PLAN_ID,
        planVersion: 3,
        grantId: GRANT_ID,
        accessToken: "operator-token",
        confirmation: `REVOKE ${GRANT_ID}`,
        reason: "safety stop",
      },
      deps(fetchImpl),
    );

    expect(calls).toEqual([
      `http://scheduler:3021/api/v1/authority-grants/${GRANT_ID}`,
      `http://scheduler:3021/api/v1/authority-grants/${GRANT_ID}/revocations`,
    ]);
  });

  test("revoke rejects a grant bound to a different plan", async () => {
    const fetchImpl = vi.fn(async () =>
      json({ ...grant, plan_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc" }),
    ) as unknown as typeof fetch;

    await expect(
      mutateControlAuthority(
        {
          action: "revoke",
          planId: PLAN_ID,
          planVersion: 3,
          grantId: GRANT_ID,
          accessToken: "operator-token",
          confirmation: `REVOKE ${GRANT_ID}`,
          reason: "safety stop",
        },
        deps(fetchImpl),
      ),
    ).rejects.toMatchObject({ status: 409 });
    expect(fetchImpl).toHaveBeenCalledOnce();
  });

  test("grant builds release, scope, and envelope only from Scheduler applicability", async () => {
    const calls: { url: string; init: RequestInit }[] = [];
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      calls.push({ url, init: init ?? {} });
      if (url.includes("applicability")) return json(applicability);
      if ((init?.method ?? "GET") === "GET") return json({}, 404);
      return json({ grant_id: GRANT_ID, status: "active" });
    }) as unknown as typeof fetch;

    await mutateControlAuthority(
      {
        action: "grant",
        planId: PLAN_ID,
        planVersion: 3,
        accessToken: "operator-token",
        confirmation: `GRANT ${PLAN_ID} v3`,
        stepUpCode: "123456",
        reason: "pilot",
        approvalRefs: ["RID-118"],
        shadowEvidenceSha256: "d".repeat(64),
        holdDrillEvidenceSha256: "e".repeat(64),
        rollbackDrillEvidenceSha256: "f".repeat(64),
        evidenceRefs: ["drill-1"],
        expiresAt: "2026-07-21T12:00:00Z",
      },
      deps(fetchImpl),
    );

    const post = calls.find((call) => call.init.method === "POST");
    expect(post?.url).toBe("http://scheduler:3021/api/v1/authority-grants");
    expect(JSON.parse(String(post?.init.body))).toMatchObject({
      plan_id: PLAN_ID,
      plan_version: 3,
      model_release_id: "model-r1",
      capability_release_id: "cap-r1",
      scope: applicability.scope,
      flow_upper_inclusive_m3s: 5,
      reason: "pilot",
    });
  });

  test("unknown actions are rejected before any upstream request", async () => {
    const fetchImpl = vi.fn() as unknown as typeof fetch;
    await expect(
      mutateControlAuthority(
        {
          action: "execute" as never,
          planId: PLAN_ID,
          planVersion: 3,
          accessToken: "token",
          confirmation: "EXECUTE",
          reason: "no",
        },
        deps(fetchImpl),
      ),
    ).rejects.toBeInstanceOf(ControlAuthorityProxyError);
    expect(fetchImpl).not.toHaveBeenCalled();
  });
});
