import { describe, expect, test, vi } from "vitest";
import {
  parseRefreshCookie,
  proxyLogin,
  proxyLogout,
  proxyRefresh,
  readSetCookie,
} from "./auth-proxy";

const b64url = (obj: object) =>
  Buffer.from(JSON.stringify(obj))
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");

const fakeJwt = (payload: object): string =>
  `${b64url({ alg: "HS256" })}.${b64url(payload)}.sig`;

const OPERATOR_TOKEN = fakeJwt({
  sub: "u1",
  email: "op@rid.go.th",
  roles: ["zone_manager"],
  type: "access",
});

type FakeResponseInit = { status?: number; setCookie?: string | null };

const upstream = (
  body: unknown,
  { status = 200, setCookie = null }: FakeResponseInit = {},
): Response =>
  ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    headers: {
      get: (k: string) => (k.toLowerCase() === "set-cookie" ? setCookie : null),
    },
  }) as unknown as Response;

const loginBody = (accessToken: string, expiresIn = 900) => ({
  success: true,
  data: {
    user: { email: "op@rid.go.th" },
    accessToken,
    tokenType: "Bearer",
    expiresIn,
  },
});

describe("parseRefreshCookie", () => {
  test.each<[string | null, string | null]>([
    [
      "refreshToken=abc.def.ghi; Max-Age=604800; Path=/; HttpOnly; SameSite=Lax",
      "abc.def.ghi",
    ],
    ["other=1, refreshToken=jwt-value; HttpOnly", "jwt-value"],
    ["session=zzz; HttpOnly", null],
    [null, null],
  ])("%j -> %j", (header, expected) => {
    expect(parseRefreshCookie(header)).toBe(expected);
  });
});

describe("readSetCookie", () => {
  test("prefers getSetCookie() and finds the refresh cookie among several lines", () => {
    const res = {
      headers: {
        getSetCookie: () => [
          "analytics=1; Path=/",
          "refreshToken=rtk; HttpOnly",
        ],
        get: () => null,
      },
    } as unknown as Response;
    expect(readSetCookie(res)).toBe("rtk");
  });

  test("falls back to a combined set-cookie header when getSetCookie is absent", () => {
    const res = {
      headers: {
        get: (k: string) =>
          k.toLowerCase() === "set-cookie"
            ? "analytics=1; Path=/, refreshToken=rtk; HttpOnly"
            : null,
      },
    } as unknown as Response;
    expect(readSetCookie(res)).toBe("rtk");
  });

  test("reads from a real Response carrying multiple Set-Cookie headers", () => {
    const headers = new Headers();
    headers.append("set-cookie", "analytics=1; Path=/");
    headers.append("set-cookie", "refreshToken=real-rtk; HttpOnly");
    expect(readSetCookie(new Response(null, { headers }))).toBe("real-rtk");
  });
});

describe("proxyLogin", () => {
  test("forwards credentials, maps the access token to a session user, and captures the refresh cookie", async () => {
    const fetchImpl = vi.fn(async () =>
      upstream(loginBody(OPERATOR_TOKEN), {
        setCookie: "refreshToken=r.t.k; HttpOnly; Path=/",
      }),
    );

    const result = await proxyLogin(
      { email: "op@rid.go.th", password: "pw" },
      { fetchImpl, authBaseUrl: "http://auth:3001" },
    );

    expect(result).toEqual({
      status: 200,
      body: {
        accessToken: OPERATOR_TOKEN,
        expiresIn: 900,
        user: { email: "op@rid.go.th", role: "operator" },
      },
      setRefreshCookie: "r.t.k",
    });
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://auth:3001/api/v1/auth/login",
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: "op@rid.go.th", password: "pw" }),
      },
    );
  });

  test("passes the upstream status and a safe message through on rejected credentials", async () => {
    const fetchImpl = vi.fn(async () =>
      upstream(
        {
          success: false,
          error: {
            code: "INVALID_CREDENTIALS",
            message: "Invalid credentials",
          },
        },
        { status: 401 },
      ),
    );

    const result = await proxyLogin(
      { email: "a@b.c", password: "x" },
      { fetchImpl },
    );

    expect(result).toEqual({
      status: 401,
      body: { error: "Invalid credentials" },
    });
  });

  test("returns 502 when the upstream omits an access token", async () => {
    const fetchImpl = vi.fn(async () => upstream({ success: true, data: {} }));
    const result = await proxyLogin(
      { email: "a@b.c", password: "x" },
      { fetchImpl },
    );
    expect(result.status).toBe(502);
  });

  test("hides upstream 5xx detail behind a generic 502 message", async () => {
    const fetchImpl = vi.fn(async () =>
      upstream(
        { error: { message: "ECONNREFUSED postgres://secret-host:5432" } },
        { status: 500 },
      ),
    );
    const result = await proxyLogin(
      { email: "a@b.c", password: "x" },
      { fetchImpl },
    );
    expect(result).toEqual({
      status: 502,
      body: { error: "Authentication service unavailable" },
    });
  });

  test("returns a generic 502 when the upstream fetch throws (network down)", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new Error("network down");
    });
    const result = await proxyLogin(
      { email: "a@b.c", password: "x" },
      { fetchImpl },
    );
    expect(result).toEqual({
      status: 502,
      body: { error: "Authentication service unavailable" },
    });
  });
});

describe("proxyRefresh", () => {
  test("returns 401 without calling upstream when there is no refresh token", async () => {
    const fetchImpl = vi.fn();
    const result = await proxyRefresh(undefined, { fetchImpl });
    expect(result.status).toBe(401);
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  test("exchanges the refresh token for a fresh session and rotates the cookie", async () => {
    const fetchImpl = vi.fn(async () =>
      upstream(
        {
          success: true,
          data: {
            accessToken: OPERATOR_TOKEN,
            tokenType: "Bearer",
            expiresIn: 900,
          },
        },
        { setCookie: "refreshToken=rotated; HttpOnly" },
      ),
    );

    const result = await proxyRefresh("old-token", {
      fetchImpl,
      authBaseUrl: "http://auth:3001",
    });

    expect(result).toEqual({
      status: 200,
      body: {
        accessToken: OPERATOR_TOKEN,
        expiresIn: 900,
        user: { email: "op@rid.go.th", role: "operator" },
      },
      setRefreshCookie: "rotated",
    });
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://auth:3001/api/v1/auth/refresh",
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ refreshToken: "old-token" }),
      },
    );
  });

  test("returns 401 when the upstream rejects the refresh token", async () => {
    const fetchImpl = vi.fn(async () =>
      upstream({ error: { message: "expired" } }, { status: 401 }),
    );
    const result = await proxyRefresh("stale", { fetchImpl });
    expect(result.status).toBe(401);
  });

  test("returns a transient 503 (not a sign-out 401) on an upstream 5xx", async () => {
    const fetchImpl = vi.fn(async () =>
      upstream({ error: { message: "db down" } }, { status: 503 }),
    );
    const result = await proxyRefresh("valid", { fetchImpl });
    expect(result).toEqual({
      status: 503,
      body: { error: "Authentication service unavailable" },
    });
  });

  test("returns a transient 503 when the upstream fetch throws", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new Error("network down");
    });
    const result = await proxyRefresh("valid", { fetchImpl });
    expect(result.status).toBe(503);
  });
});

describe("proxyLogout", () => {
  test("revokes the refresh token upstream and clears the cookie", async () => {
    const fetchImpl = vi.fn(async () => upstream({ success: true }));
    const result = await proxyLogout("rtk", {
      fetchImpl,
      authBaseUrl: "http://auth:3001",
    });

    expect(result).toEqual({
      status: 200,
      body: { ok: true },
      clearRefreshCookie: true,
    });
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://auth:3001/api/v1/auth/logout",
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ refreshToken: "rtk" }),
      },
    );
  });

  test("still clears the cookie (and skips upstream) when there is no token", async () => {
    const fetchImpl = vi.fn();
    const result = await proxyLogout(undefined, { fetchImpl });
    expect(result).toEqual({
      status: 200,
      body: { ok: true },
      clearRefreshCookie: true,
    });
    expect(fetchImpl).not.toHaveBeenCalled();
  });
});
