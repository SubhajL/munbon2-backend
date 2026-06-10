import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { LoginScreen } from "./page";
import { AuthProvider, type AuthClient } from "@/components/AuthProvider";
import { AuthError, type Session } from "@/lib/auth-client";

const { replace } = vi.hoisted(() => ({ replace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => new URLSearchParams("next=/gates/waste-way"),
}));

const session: Session = {
  accessToken: "a.b.c",
  expiresIn: 900,
  user: { email: "op@rid.go.th", role: "operator" },
};

const stub = (over: Partial<AuthClient> = {}): AuthClient => ({
  login: vi.fn(async () => session),
  refresh: vi.fn(async () => null),
  logout: vi.fn(async () => {}),
  ...over,
});

const renderLogin = (client: AuthClient) =>
  render(
    <AuthProvider client={client}>
      <LoginScreen />
    </AuthProvider>,
  );

describe("LoginScreen", () => {
  test("signs in and redirects to the requested next path", async () => {
    const client = stub();
    renderLogin(client);

    await userEvent.type(screen.getByLabelText(/email/i), "op@rid.go.th");
    await userEvent.type(screen.getByLabelText(/password/i), "pw");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/gates/waste-way"),
    );
    expect(client.login).toHaveBeenCalledWith({
      email: "op@rid.go.th",
      password: "pw",
    });
  });

  test("shows the auth error message when credentials are rejected", async () => {
    renderLogin(
      stub({
        login: vi.fn(async () => {
          throw new AuthError("Invalid credentials", 401);
        }),
      }),
    );

    await userEvent.type(screen.getByLabelText(/email/i), "a@b.c");
    await userEvent.type(screen.getByLabelText(/password/i), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid credentials",
    );
  });
});
