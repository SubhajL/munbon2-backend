import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import {
  AuthProvider,
  useAuth,
  type AuthClient,
  type RefreshLock,
} from "./AuthProvider";
import type { Session } from "@/lib/auth-client";

const b64url = (obj: object) =>
  Buffer.from(JSON.stringify(obj))
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
const fakeJwt = (payload: object) =>
  `${b64url({ alg: "HS256" })}.${b64url(payload)}.sig`;

const operatorSession: Session = {
  accessToken: fakeJwt({ email: "op@rid.go.th", roles: ["zone_manager"] }),
  expiresIn: 900,
  user: { email: "op@rid.go.th", role: "operator" },
};

function Consumer() {
  const { status, session, login, logout, refresh, getToken } = useAuth();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="email">{session?.user.email ?? "none"}</span>
      <span data-testid="role">{session?.user.role ?? "none"}</span>
      <span data-testid="token">{getToken() ?? "none"}</span>
      <button onClick={() => login("op@rid.go.th", "pw").catch(() => {})}>
        login
      </button>
      <button onClick={() => logout()}>logout</button>
      <button
        onClick={() => {
          void refresh();
          void refresh();
        }}
      >
        double-refresh
      </button>
    </div>
  );
}

const stubClient = (over: Partial<AuthClient> = {}): AuthClient => ({
  login: vi.fn(async () => operatorSession),
  refresh: vi.fn(async () => null),
  logout: vi.fn(async () => {}),
  ...over,
});

describe("AuthProvider", () => {
  test("restores a session on mount via the refresh cookie", async () => {
    const client = stubClient({ refresh: vi.fn(async () => operatorSession) });
    render(
      <AuthProvider client={client}>
        <Consumer />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("authenticated"),
    );
    expect(screen.getByTestId("email")).toHaveTextContent("op@rid.go.th");
    expect(screen.getByTestId("role")).toHaveTextContent("operator");
    expect(client.refresh).toHaveBeenCalledTimes(1);
  });

  test("lands on unauthenticated when there is no valid refresh cookie", async () => {
    render(
      <AuthProvider client={stubClient()}>
        <Consumer />
      </AuthProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated"),
    );
    expect(screen.getByTestId("token")).toHaveTextContent("none");
  });

  test("login establishes an in-memory session exposed via getToken", async () => {
    const client = stubClient();
    render(
      <AuthProvider client={client}>
        <Consumer />
      </AuthProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated"),
    );

    await userEvent.click(screen.getByRole("button", { name: "login" }));

    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("authenticated"),
    );
    expect(client.login).toHaveBeenCalledWith({
      email: "op@rid.go.th",
      password: "pw",
    });
    expect(screen.getByTestId("token")).toHaveTextContent(
      operatorSession.accessToken,
    );
  });

  test("logout revokes the session and returns to unauthenticated", async () => {
    const client = stubClient({ refresh: vi.fn(async () => operatorSession) });
    render(
      <AuthProvider client={client}>
        <Consumer />
      </AuthProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("authenticated"),
    );

    await userEvent.click(screen.getByRole("button", { name: "logout" }));

    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated"),
    );
    expect(client.logout).toHaveBeenCalledTimes(1);
  });

  test("coalesces concurrent refreshes into a single upstream call", async () => {
    let resolveRefresh: (s: Session | null) => void = () => {};
    const refreshFn = vi.fn(
      () => new Promise<Session | null>((r) => (resolveRefresh = r)),
    );
    render(
      <AuthProvider client={stubClient({ refresh: refreshFn })}>
        <Consumer />
      </AuthProvider>,
    );

    // The mount refresh is still in flight; firing two more must not re-call.
    await userEvent.click(
      screen.getByRole("button", { name: "double-refresh" }),
    );
    expect(refreshFn).toHaveBeenCalledTimes(1);

    resolveRefresh(operatorSession);
    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("authenticated"),
    );
  });

  test("keeps the current session on a transient refresh failure (no sign-out)", async () => {
    const refreshFn = vi
      .fn<AuthClient["refresh"]>()
      .mockResolvedValueOnce(operatorSession) // mount restores the session
      .mockRejectedValueOnce(new Error("503 transient")); // later renewal fails
    render(
      <AuthProvider client={stubClient({ refresh: refreshFn })}>
        <Consumer />
      </AuthProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("authenticated"),
    );

    await userEvent.click(
      screen.getByRole("button", { name: "double-refresh" }),
    );
    await waitFor(() => expect(refreshFn).toHaveBeenCalledTimes(2));

    // Transient failure must NOT log the user out.
    expect(screen.getByTestId("status")).toHaveTextContent("authenticated");
  });

  test("serializes refreshes through the Web Locks API when available", async () => {
    const requestSpy = vi.fn();
    const locks: RefreshLock = {
      request: <T,>(name: string, cb: () => Promise<T>) => {
        requestSpy(name, cb);
        return cb();
      },
    };
    render(
      <AuthProvider
        client={stubClient({ refresh: vi.fn(async () => operatorSession) })}
        locks={locks}
      >
        <Consumer />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("authenticated"),
    );
    expect(requestSpy).toHaveBeenCalledWith(
      "sgc-refresh-token",
      expect.any(Function),
    );
  });

  test("with a dev token, authenticates synthetically and never calls refresh", async () => {
    const client = stubClient();
    render(
      <AuthProvider
        client={client}
        devToken={fakeJwt({ email: "dev@rid.go.th", roles: ["rid_admin"] })}
      >
        <Consumer />
      </AuthProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("status")).toHaveTextContent("authenticated"),
    );
    expect(screen.getByTestId("role")).toHaveTextContent("admin");
    expect(client.refresh).not.toHaveBeenCalled();
  });
});
