import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test, vi } from "vitest";
import { RequireAuth } from "./RequireAuth";
import { AuthProvider, type AuthClient } from "./AuthProvider";

const { replace } = vi.hoisted(() => ({ replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/gates/waste-way",
}));

const b64url = (obj: object) =>
  Buffer.from(JSON.stringify(obj))
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
const operatorToken = `${b64url({ alg: "HS256" })}.${b64url({ email: "op@rid.go.th", roles: ["zone_manager"] })}.sig`;

const stubClient = (over: Partial<AuthClient> = {}): AuthClient => ({
  login: vi.fn(async () => {
    throw new Error("unused");
  }),
  refresh: vi.fn(async () => null),
  logout: vi.fn(async () => {}),
  ...over,
});

const renderGuard = (props: { client?: AuthClient; devToken?: string }) =>
  render(
    <AuthProvider
      client={props.client ?? stubClient()}
      devToken={props.devToken}
    >
      <RequireAuth>
        <div data-testid="protected">secret</div>
      </RequireAuth>
    </AuthProvider>,
  );

afterEach(() => replace.mockClear());

describe("RequireAuth", () => {
  test("renders the protected content and an account badge when authenticated", async () => {
    renderGuard({ devToken: operatorToken });

    expect(await screen.findByTestId("protected")).toBeInTheDocument();
    expect(screen.getByText("op@rid.go.th")).toBeInTheDocument();
    expect(screen.getByText("operator")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /log out|ออกจากระบบ/i }),
    ).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  test("redirects to /login with the current path when unauthenticated", async () => {
    renderGuard({ client: stubClient() });

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/login?next=%2Fgates%2Fwaste-way"),
    );
    expect(screen.queryByTestId("protected")).not.toBeInTheDocument();
  });

  test("shows neither content nor a redirect while the session is still loading", async () => {
    renderGuard({
      client: stubClient({ refresh: () => new Promise<null>(() => {}) }),
    });

    expect(screen.queryByTestId("protected")).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  test("logging out revokes the session", async () => {
    const client = stubClient();
    renderGuard({ client, devToken: operatorToken });
    await screen.findByTestId("protected");

    await userEvent.click(
      screen.getByRole("button", { name: /log out|ออกจากระบบ/i }),
    );

    expect(client.logout).toHaveBeenCalledTimes(1);
  });
});
