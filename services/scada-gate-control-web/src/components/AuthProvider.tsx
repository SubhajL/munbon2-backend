"use client";

/**
 * Holds the auth session for the SPA. The access token lives only in memory
 * (never in storage); the httpOnly refresh cookie — set same-origin by the
 * `/api/auth/*` route handlers — is what survives reloads. On mount we silently
 * exchange that cookie for a fresh session. A `devToken` escape hatch skips the
 * whole flow for local/offline development.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  login as defaultLogin,
  logout as defaultLogout,
  refresh as defaultRefresh,
  type Session,
} from "@/lib/auth-client";
import { DEV_TOKEN } from "@/lib/config";
import { userFromToken } from "@/lib/role";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

export type AuthClient = {
  login: (credentials: { email: string; password: string }) => Promise<Session>;
  refresh: () => Promise<Session | null>;
  logout: () => Promise<void>;
};

export type AuthContextValue = {
  status: AuthStatus;
  session: Session | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  /** Refreshes the access token; resolves to the new token or null if signed out. */
  refresh: () => Promise<string | null>;
  /** Reads the current access token without re-rendering (stable identity). */
  getToken: () => string | undefined;
};

const DEFAULT_CLIENT: AuthClient = {
  login: defaultLogin,
  refresh: defaultRefresh,
  logout: defaultLogout,
};

const AuthContext = createContext<AuthContextValue | null>(null);

const devSession = (token: string): Session => ({
  accessToken: token,
  expiresIn: 0,
  user: userFromToken(token),
});

/** Minimal slice of the Web Locks API used to serialize refreshes across tabs. */
export type RefreshLock = {
  request<T>(name: string, callback: () => Promise<T>): Promise<T>;
};

const REFRESH_LOCK = "sgc-refresh-token";

const DEFAULT_LOCKS: RefreshLock | undefined =
  typeof navigator !== "undefined" && "locks" in navigator
    ? (navigator.locks as unknown as RefreshLock)
    : undefined;

export function AuthProvider({
  children,
  client = DEFAULT_CLIENT,
  devToken = DEV_TOKEN,
  locks = DEFAULT_LOCKS,
}: {
  children: ReactNode;
  client?: AuthClient;
  devToken?: string;
  locks?: RefreshLock;
}) {
  // Seed the dev-token session as initial state so the effect never has to
  // setState synchronously for the escape-hatch path.
  const [session, setSession] = useState<Session | null>(() =>
    devToken ? devSession(devToken) : null,
  );
  const [status, setStatus] = useState<AuthStatus>(() =>
    devToken ? "authenticated" : "loading",
  );
  const tokenRef = useRef<string | undefined>(devToken);

  const refreshInFlight = useRef<Promise<string | null> | null>(null);

  const apply = useCallback((next: Session | null) => {
    tokenRef.current = next?.accessToken;
    setSession(next);
    setStatus(next ? "authenticated" : "unauthenticated");
  }, []);

  // Coalesces refreshes so the rotating refresh token is never spent twice and
  // invalidated against itself: in-memory dedup handles concurrent callers in
  // THIS tab; the Web Lock (when available) serializes ACROSS tabs — each tab
  // then reads the freshly-rotated shared cookie in turn.
  const runRefresh = useCallback((): Promise<string | null> => {
    if (refreshInFlight.current) return refreshInFlight.current;
    const exchange = (): Promise<string | null> =>
      client.refresh().then((restored) => {
        // `null` means the server said the session is gone -> sign out.
        apply(restored);
        return restored?.accessToken ?? null;
      });
    const inFlight = (
      locks ? locks.request(REFRESH_LOCK, exchange) : exchange()
    )
      .catch(() => {
        // Transient failure (network / 5xx): keep an existing session and only
        // fall back to unauthenticated when we never had one (initial load).
        if (!tokenRef.current) apply(null);
        return null;
      })
      .finally(() => {
        refreshInFlight.current = null;
      });
    refreshInFlight.current = inFlight;
    return inFlight;
  }, [apply, client, locks]);

  useEffect(() => {
    if (devToken) return; // dev token is already seeded; never hit the network
    void runRefresh();
  }, [devToken, runRefresh]);

  const login = useCallback(
    async (email: string, password: string) => {
      apply(await client.login({ email, password }));
    },
    [apply, client],
  );

  const logout = useCallback(async () => {
    await client.logout();
    apply(null);
  }, [apply, client]);

  const refresh = useCallback(
    (): Promise<string | null> =>
      devToken ? Promise.resolve(tokenRef.current ?? null) : runRefresh(),
    [devToken, runRefresh],
  );

  const getToken = useCallback(() => tokenRef.current, []);

  return (
    <AuthContext.Provider
      value={{ status, session, login, logout, refresh, getToken }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
