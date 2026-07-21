import { describe, expect, test, vi } from "vitest";
import {
  ControlAuthorityApiError,
  createControlAuthorityClient,
} from "./control-authority-api";

const PLAN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

describe("createControlAuthorityClient", () => {
  test("reads the same-origin dashboard with no-store and bearer", async () => {
    const fetchImpl = vi.fn(async () => Response.json({ applicability: {} })) as unknown as typeof fetch;
    const client = createControlAuthorityClient({
      fetchImpl,
      getToken: () => "operator-token",
    });

    await client.read(PLAN_ID, 3);

    expect(fetchImpl).toHaveBeenCalledWith(
      `/api/control-authority?planId=${PLAN_ID}&planVersion=3`,
      {
        cache: "no-store",
        headers: { authorization: "Bearer operator-token" },
      },
    );
  });

  test("mutation forwards exact confirmation and optional TOTP", async () => {
    const fetchImpl = vi.fn(async () => Response.json({ status: "held" })) as unknown as typeof fetch;
    const client = createControlAuthorityClient({
      fetchImpl,
      getToken: () => "operator-token",
    });

    await client.mutate(
      {
        action: "hold",
        planId: PLAN_ID,
        planVersion: 3,
        reason: "safety stop",
      },
      `HOLD ${PLAN_ID} v3`,
    );

    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/control-authority",
      expect.objectContaining({
        method: "POST",
        cache: "no-store",
        headers: {
          authorization: "Bearer operator-token",
          "content-type": "application/json",
          "x-operator-confirmation": `HOLD ${PLAN_ID} v3`,
        },
      }),
    );
  });

  test("refreshes once after 401 and retries with the new token", async () => {
    const tokens: string[] = [];
    let call = 0;
    const fetchImpl = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      tokens.push((init?.headers as Record<string, string>).authorization);
      call += 1;
      return call === 1 ? new Response(null, { status: 401 }) : Response.json({});
    }) as unknown as typeof fetch;
    const client = createControlAuthorityClient({
      fetchImpl,
      getToken: () => "expired",
      onUnauthorized: async () => "fresh",
    });

    await client.read(PLAN_ID, 3);

    expect(tokens).toEqual(["Bearer expired", "Bearer fresh"]);
  });

  test("never turns an upstream failure into stale success", async () => {
    const fetchImpl = vi.fn(async () =>
      Response.json({ error: "down" }, { status: 503 }),
    ) as unknown as typeof fetch;
    const client = createControlAuthorityClient({ fetchImpl });

    await expect(client.read(PLAN_ID, 3)).rejects.toBeInstanceOf(
      ControlAuthorityApiError,
    );
  });
});
