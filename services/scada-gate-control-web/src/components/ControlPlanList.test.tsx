import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, test } from "vitest";
import { ControlPlanList } from "./ControlPlanList";
import type { ControlPlanSummary } from "@/lib/control-plans-api";

const plans: ControlPlanSummary[] = [
  {
    plan_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    plan_version: 3,
    campaign_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    lifecycle_state: "shadow_active",
    approval_trust: true,
    requirement_run_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    requirement_version: 4,
    input_content_hash: "1".repeat(64),
    model_snapshot_id: "snapshot-r1",
    model_release_content_hash: "2".repeat(64),
    optimizer_status: "feasible",
    prediction_status: "completed",
    prediction_run_id: "c".repeat(64),
    prediction_response_sha256: "d".repeat(64),
    created_by_subject: "operator-7",
    horizon_start: "2026-07-20T00:00:00+00:00",
    horizon_end: "2026-07-21T00:00:00+00:00",
    created_at: "2026-07-19T20:00:00+00:00",
  },
  {
    plan_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    plan_version: 1,
    campaign_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
    lifecycle_state: "invalidated",
    approval_trust: false,
    requirement_run_id: "ffffffff-ffff-4fff-8fff-ffffffffffff",
    requirement_version: 1,
    input_content_hash: "3".repeat(64),
    model_snapshot_id: "snapshot-r2",
    model_release_content_hash: "4".repeat(64),
    optimizer_status: "infeasible",
    prediction_status: "not_requested",
    prediction_run_id: null,
    prediction_response_sha256: null,
    created_by_subject: "operator-8",
    horizon_start: "2026-07-20T00:00:00+00:00",
    horizon_end: "2026-07-21T00:00:00+00:00",
    created_at: "2026-07-19T21:00:00+00:00",
  },
];

describe("ControlPlanList", () => {
  test("renders each plan's exact lifecycle/status verbatim, linking to a read-only detail", () => {
    render(<ControlPlanList plans={plans} />);
    expect(screen.getByTestId("lifecycle-aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")).toHaveTextContent(
      "shadow_active",
    );
    // infeasible/invalidated are preserved verbatim, never collapsed to a success indicator.
    expect(screen.getByText("invalidated")).toBeInTheDocument();
    expect(screen.getByText("infeasible")).toBeInTheDocument();
    const link = screen.getAllByRole("link")[0];
    expect(link).toHaveAttribute(
      "href",
      "/control-plans/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/versions/3",
    );
  });

  test("is read-only — no command controls", () => {
    const { container } = render(<ControlPlanList plans={plans} />);
    expect(container.querySelectorAll("button, form, input, [role='button']")).toHaveLength(0);
  });

  test("has no accessibility violations", async () => {
    const { container } = render(<ControlPlanList plans={plans} />);
    expect(await axe(container)).toHaveNoViolations();
  });

  test("shows an explicit empty state, never a fabricated row", () => {
    render(<ControlPlanList plans={[]} />);
    expect(screen.getByText(/No shadow control plans/i)).toBeInTheDocument();
  });
});
