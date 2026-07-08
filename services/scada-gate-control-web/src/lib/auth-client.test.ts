import { describe, expect, test, vi } from "vitest";
import { AuthError, login, logout, refresh, type Session } from "./auth-client";

const jsonResponse = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

const session: Session = {
  accessToken: "a.b.c",
  expiresIn: 900,
  user: { email: "op@rid.go.th", role: "operator" },
};

describe("login", () => {
  test("POSTs credentials to the same-origin proxy and returns the session", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(session));

    expect(
      await login({ email: "op@rid.go.th", password: "pw" }, { fetchImpl }),
    ).toEqual(session);
    expect(fetchImpl).toHaveBeenCalledWith("/api/auth/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ email: "op@rid.go.th", password: "pw" }),
    });
  });

  test("throws AuthError carrying the status and message on rejected credentials", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({ error: "Invalid credentials" }, 401),
    );
    await expect(
      login({ email: "a@b.c", password: "x" }, { fetchImpl }),
    ).rejects.toMatchObject({
      status: 401,
      message: "Invalid credentials",
    });
    await expect(
      login({ email: "a@b.c", password: "x" }, { fetchImpl }),
    ).rejects.toBeInstanceOf(AuthError);
  });
});

describe("refresh", () => {
  test("returns the rotated session when the refresh cookie is still valid", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(session));
    expect(await refresh({ fetchImpl })).toEqual(session);
    expect(fetchImpl).toHaveBeenCalledWith("/api/auth/refresh", {
      method: "POST",
      credentials: "same-origin",
    });
  });

  test("returns null (definitive sign-out) on a 401", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({ error: "No active session" }, 401),
    );
    expect(await refresh({ fetchImpl })).toBeNull();
  });

  test("throws on a transient 5xx so the caller can keep the current session", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({ error: "Authentication service unavailable" }, 503),
    );
    await expect(refresh({ fetchImpl })).rejects.toMatchObject({ status: 503 });
    await expect(refresh({ fetchImpl })).rejects.toBeInstanceOf(AuthError);
  });

  test("propagates a network error (transient) rather than signalling sign-out", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new Error("network down");
    });
    await expect(refresh({ fetchImpl })).rejects.toThrow("network down");
  });
});

describe("logout", () => {
  test("POSTs to the logout proxy and resolves even when the request fails", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new Error("network down");
    });
    await expect(logout({ fetchImpl })).resolves.toBeUndefined();
    expect(fetchImpl).toHaveBeenCalledWith("/api/auth/logout", {
      method: "POST",
      credentials: "same-origin",
    });
  });
});
