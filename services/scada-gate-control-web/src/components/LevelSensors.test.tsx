import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { LevelSensors } from "./LevelSensors";

describe("LevelSensors", () => {
  test("marks the current level ON and makes it non-actionable", () => {
    render(<LevelSensors currentLevel={2} canCommand onCommand={() => {}} />);
    const current = screen.getByRole("button", {
      name: /เปิดระดับ 1 \(Level 2\)/,
    });
    expect(current).toBeDisabled();
    expect(current).toHaveAttribute("aria-pressed", "true");
  });

  test("clicking an OFF level requests a command for that level", async () => {
    const onCommand = vi.fn();
    render(<LevelSensors currentLevel={2} canCommand onCommand={onCommand} />);
    await userEvent.click(
      screen.getByRole("button", { name: /เปิด 100% \(Level 4\)/ }),
    );
    expect(onCommand).toHaveBeenCalledWith(4);
  });

  test("a viewer cannot command — OFF levels are disabled", () => {
    render(
      <LevelSensors currentLevel={2} canCommand={false} onCommand={() => {}} />,
    );
    expect(
      screen.getByRole("button", { name: /ปิด \(Level 1\)/ }),
    ).toBeDisabled();
  });
});
