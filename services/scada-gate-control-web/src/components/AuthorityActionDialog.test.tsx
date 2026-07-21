import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { AuthorityActionDialog } from "./AuthorityActionDialog";

const PLAN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

describe("AuthorityActionDialog", () => {
  test("requires the exact bound phrase and TOTP for positive actions", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(
      <AuthorityActionDialog
        open
        action="activate"
        planId={PLAN_ID}
        planVersion={3}
        pending={false}
        onSubmit={onSubmit}
        onCancel={() => undefined}
      />,
    );

    await user.type(screen.getByLabelText(/reason/i), "operator checkpoint");
    await user.type(screen.getByLabelText(/evidence references/i), "RID-118");
    await user.type(screen.getByLabelText(/TOTP/i), "123456");
    await user.type(
      screen.getByLabelText(/exact confirmation/i),
      `activate ${PLAN_ID} v3`,
    );
    expect(screen.getByRole("button", { name: /confirm activate/i })).toBeDisabled();

    await user.clear(screen.getByLabelText(/exact confirmation/i));
    await user.type(
      screen.getByLabelText(/exact confirmation/i),
      `ACTIVATE ${PLAN_ID} v3`,
    );
    await user.click(screen.getByRole("button", { name: /confirm activate/i }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        mutation: expect.objectContaining({
          action: "activate",
          planId: PLAN_ID,
          planVersion: 3,
          reason: "operator checkpoint",
          approvalRefs: ["RID-118"],
        }),
        confirmation: `ACTIVATE ${PLAN_ID} v3`,
        stepUpCode: "123456",
      }),
    );
  });

  test("hold requires confirmation but has no TOTP or evidence inputs", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(
      <AuthorityActionDialog
        open
        action="hold"
        planId={PLAN_ID}
        planVersion={3}
        pending={false}
        onSubmit={onSubmit}
        onCancel={() => undefined}
      />,
    );

    expect(screen.queryByLabelText(/TOTP/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/evidence references/i)).not.toBeInTheDocument();
    await user.type(screen.getByLabelText(/reason/i), "safety stop");
    await user.type(
      screen.getByLabelText(/exact confirmation/i),
      `HOLD ${PLAN_ID} v3`,
    );
    await user.click(screen.getByRole("button", { name: /confirm hold/i }));

    expect(onSubmit).toHaveBeenCalledWith({
      mutation: {
        action: "hold",
        planId: PLAN_ID,
        planVersion: 3,
        reason: "safety stop",
      },
      confirmation: `HOLD ${PLAN_ID} v3`,
      stepUpCode: undefined,
    });
  });
});
