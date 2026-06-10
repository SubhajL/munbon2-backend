import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, test, vi } from "vitest";
import { LoginForm } from "./LoginForm";

describe("LoginForm", () => {
  test("submits the typed email and password", async () => {
    const onSubmit = vi.fn();
    render(<LoginForm onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText(/email/i), "op@rid.go.th");
    await userEvent.type(screen.getByLabelText(/password/i), "s3cret");
    await userEvent.click(screen.getByRole("button"));

    expect(onSubmit).toHaveBeenCalledWith("op@rid.go.th", "s3cret");
  });

  test("surfaces an error message as an alert", () => {
    render(<LoginForm onSubmit={vi.fn()} error="Invalid credentials" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Invalid credentials");
  });

  test("disables the submit button while a sign-in is pending", () => {
    render(<LoginForm onSubmit={vi.fn()} pending />);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  test("has no accessibility violations", async () => {
    const { container } = render(<LoginForm onSubmit={vi.fn()} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
