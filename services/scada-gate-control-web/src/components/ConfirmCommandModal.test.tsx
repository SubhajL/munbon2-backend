import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, test, vi } from "vitest";
import { ConfirmCommandModal } from "./ConfirmCommandModal";

describe("ConfirmCommandModal", () => {
  test("renders the title, body and raw Modbus details when open", () => {
    render(
      <ConfirmCommandModal
        open
        gateName="Waste Way"
        level={2}
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    expect(screen.getByRole("dialog")).toHaveTextContent(
      "ยืนยันการสั่งงานประตูน้ำ",
    );
    expect(
      screen.getByText("ต้องการสั่ง Waste Way ไปที่ เปิดระดับ 1 ใช่หรือไม่?"),
    ).toBeInTheDocument();
    expect(screen.getByText("Op_gate Address 108 = 2")).toBeInTheDocument();
    expect(screen.getByText("GateCF Address 17 = 1")).toBeInTheDocument();
  });

  test("confirm and cancel buttons fire their handlers", async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
      <ConfirmCommandModal
        open
        gateName="Waste Way"
        level={3}
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "ยืนยันการสั่งงาน" }));
    expect(onConfirm).toHaveBeenCalledOnce();
    await user.click(screen.getByRole("button", { name: "ยกเลิก" }));
    expect(onCancel).toHaveBeenCalledOnce();
  });

  test("renders no dialog when closed", () => {
    render(
      <ConfirmCommandModal
        open={false}
        gateName="Waste Way"
        level={2}
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  test("has no accessibility violations", async () => {
    const { baseElement } = render(
      <ConfirmCommandModal
        open
        gateName="Waste Way"
        level={2}
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    expect(await axe(baseElement)).toHaveNoViolations();
  });
});
