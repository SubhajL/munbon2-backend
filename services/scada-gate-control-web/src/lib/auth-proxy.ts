/**
 * Server-only logic for the auth BFF proxy (`/api/auth/*` route handlers). The
 * browser never talks to `services/auth` directly: these helpers call it
 * server-side, translate its responses into the session shape the SPA needs,
 * and surface the refresh token so the route handler can re-issue it as a
 * SAME-ORIGIN, httpOnly cookie. Kept free of `next/*` imports so it is unit
 * testable with an injected fetch.
 */
import { userFromToken, type AppRole } from "./role";

const AUTH_SERVICE_URL =
  process.env.AUTH_SERVICE_URL ?? "http://localhost:3001";

/** Name of the same-origin httpOnly cookie holding the upstream refresh token. */
export const REFRESH_COOKIE = "sgc_refresh";

/** Shown to the browser instead of leaking upstream 5xx/internal detail. */
const SERVICE_UNAVAILABLE = "Authentication service unavailable";

export type SessionUser = { email: string | null; role: AppRole };
export type AuthResult = {
  accessToken: string;
  expiresIn: number;
  user: SessionUser;
};

export type ProxyResponse = {
  status: number;
  body: AuthResult | { error: string } | { ok: true };
  setRefreshCookie?: string;
  clearRefreshCookie?: boolean;
};

type ProxyDeps = { fetchImpl?: typeof fetch; authBaseUrl?: string };

/** Extracts the `refreshToken` value from one or a combined `Set-Cookie` line. */
export function parseRefreshCookie(setCookie: string | null): string | null {
  if (!setCookie) return null;
  // The value is a JWT — no `;`, `,`, or whitespace — so this stays unambiguous
  // even when several cookies are collapsed into one comma-joined header.
  const match = /refreshToken=([^;,\s]+)/.exec(setCookie);
  return match ? match[1].trim() : null;
}

/**
 * Reads the refresh cookie from a response. Prefers `getSetCookie()` (which
 * returns each `Set-Cookie` as its own line) and only falls back to the legacy
 * combined `get('set-cookie')` string when the runtime lacks it.
 */
export function readSetCookie(res: Response): string | null {
  const headers = res.headers as Headers & { getSetCookie?: () => string[] };
  const lines = headers.getSetCookie?.();
  if (lines && lines.length > 0) {
    for (const line of lines) {
      const value = parseRefreshCookie(line);
      if (value) return value;
    }
    return null;
  }
  return parseRefreshCookie(headers.get("set-cookie"));
}

function authResult(accessToken: string, expiresIn: unknown): AuthResult {
  return {
    accessToken,
    expiresIn: typeof expiresIn === "number" ? expiresIn : 0,
    user: userFromToken(accessToken),
  };
}

function upstreamError(payload: unknown): string {
  const message = (payload as { error?: { message?: unknown } })?.error
    ?.message;
  return typeof message === "string" ? message : "Authentication failed";
}

type FailureMapper = (status: number, message: string) => ProxyResponse;

async function exchange(
  res: Response,
  onFailure: FailureMapper,
): Promise<ProxyResponse> {
  const payload = (await res.json().catch(() => null)) as {
    data?: { accessToken?: unknown; expiresIn?: unknown };
  } | null;

  if (!res.ok) return onFailure(res.status, upstreamError(payload));

  const accessToken = payload?.data?.accessToken;
  if (typeof accessToken !== "string") {
    return { status: 502, body: { error: SERVICE_UNAVAILABLE } };
  }

  return {
    status: 200,
    body: authResult(accessToken, payload?.data?.expiresIn),
    setRefreshCookie: readSetCookie(res) ?? undefined,
  };
}

// Login: 4xx (bad credentials / validation) carries a user-actionable message;
// 5xx is an upstream fault whose detail must not reach the browser.
const loginFailure: FailureMapper = (status, message) =>
  status >= 500
    ? { status: 502, body: { error: SERVICE_UNAVAILABLE } }
    : { status, body: { error: message } };

// Refresh: a 4xx means the session is genuinely invalid -> sign the user out;
// a 5xx is transient and must NOT masquerade as a sign-out (503, not 401).
const refreshFailure: FailureMapper = (status) =>
  status >= 500
    ? { status: 503, body: { error: SERVICE_UNAVAILABLE } }
    : { status: 401, body: { error: "Session expired" } };

function post(deps: ProxyDeps, path: string, body: unknown): Promise<Response> {
  const doFetch = deps.fetchImpl ?? fetch;
  const baseUrl = deps.authBaseUrl ?? AUTH_SERVICE_URL;
  return doFetch(`${baseUrl}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function proxyLogin(
  credentials: { email: string; password: string },
  deps: ProxyDeps = {},
): Promise<ProxyResponse> {
  try {
    const res = await post(deps, "/api/v1/auth/login", credentials);
    return await exchange(res, loginFailure);
  } catch {
    return { status: 502, body: { error: SERVICE_UNAVAILABLE } };
  }
}

export async function proxyRefresh(
  refreshToken: string | undefined,
  deps: ProxyDeps = {},
): Promise<ProxyResponse> {
  if (!refreshToken)
    return { status: 401, body: { error: "No active session" } };
  try {
    const res = await post(deps, "/api/v1/auth/refresh", { refreshToken });
    return await exchange(res, refreshFailure);
  } catch {
    // Network/availability failure — transient, not a sign-out.
    return { status: 503, body: { error: SERVICE_UNAVAILABLE } };
  }
}

export async function proxyLogout(
  refreshToken: string | undefined,
  deps: ProxyDeps = {},
): Promise<ProxyResponse> {
  if (refreshToken) {
    // Best-effort revocation; the cookie is cleared regardless of the outcome.
    await post(deps, "/api/v1/auth/logout", { refreshToken }).catch(() => null);
  }
  return { status: 200, body: { ok: true }, clearRefreshCookie: true };
}
