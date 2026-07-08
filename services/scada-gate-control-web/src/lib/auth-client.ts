/**
 * Browser-side client for the app's OWN auth BFF (`/api/auth/*` route handlers).
 * Everything is same-origin, so the httpOnly refresh cookie rides along
 * automatically; the access token is returned in the body for in-memory use.
 */
import type { SessionUser } from "./auth-proxy";

export type { SessionUser };
export type Session = {
  accessToken: string;
  expiresIn: number;
  user: SessionUser;
};

export class AuthError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "AuthError";
  }
}

type AuthClientDeps = { fetchImpl?: typeof fetch };

const errorMessage = async (res: Response): Promise<string> => {
  const body = (await res.json().catch(() => null)) as {
    error?: unknown;
  } | null;
  return typeof body?.error === "string"
    ? body.error
    : `Request failed (${res.status})`;
};

export async function login(
  credentials: { email: string; password: string },
  deps: AuthClientDeps = {},
): Promise<Session> {
  const doFetch = deps.fetchImpl ?? fetch;
  const res = await doFetch("/api/auth/login", {
    method: "POST",
    headers: { "content-type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(credentials),
  });
  if (!res.ok) throw new AuthError(await errorMessage(res), res.status);
  return (await res.json()) as Session;
}

/**
 * Silently exchanges the refresh cookie for a fresh session.
 * - resolves a `Session` on success;
 * - resolves `null` ONLY when the server says the session is gone (401) — a
 *   definitive sign-out;
 * - THROWS on a transient failure (5xx / network) so the caller can keep the
 *   current in-memory session instead of logging the user out.
 */
export async function refresh(
  deps: AuthClientDeps = {},
): Promise<Session | null> {
  const doFetch = deps.fetchImpl ?? fetch;
  const res = await doFetch("/api/auth/refresh", {
    method: "POST",
    credentials: "same-origin",
  });
  if (res.status === 401) return null;
  if (!res.ok) throw new AuthError(await errorMessage(res), res.status);
  return (await res.json()) as Session;
}

export async function logout(deps: AuthClientDeps = {}): Promise<void> {
  const doFetch = deps.fetchImpl ?? fetch;
  await doFetch("/api/auth/logout", {
    method: "POST",
    credentials: "same-origin",
  }).catch(() => null);
}
