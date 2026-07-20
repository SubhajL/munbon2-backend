import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, test } from "vitest";
import { ControlPlanDetail, type ControlPlanDetailData } from "./ControlPlanDetail";

const PLAN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

function data(overrides: Partial<ControlPlanDetailData> = {}): ControlPlanDetailData {
  return {
    planId: PLAN_ID,
    planVersion: 3,
    lifecycleState: "shadow_active",
    coverage: {
      plan_id: PLAN_ID,
      plan_version: 3,
      optimizer_status: "feasible",
      prediction_status: "completed",
      prediction_run_id: "c".repeat(64),
      prediction_member_statuses: [
        { member: "lower", status: "completed" },
        { member: "nominal", status: "completed" },
        { member: "upper", status: "completed" },
      ],
    },
    timeline: {
      plan_id: PLAN_ID,
      plan_version: 3,
      intents: [
        {
          intent_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
          canonical_gate_id: "M(0,0;1,0)",
          event_kind: "open",
          event_sequence: 1,
          not_before: "2026-07-20T06:00:00+00:00",
          deadline: "2026-07-21T00:00:00+00:00",
          execution_state: "claimed",
          claimed_at: "2026-07-20T06:05:00+00:00",
          receipt_status: "validation_accepted",
          reason_code: null,
          validated_at: "2026-07-20T06:05:01+00:00",
          dispatched_at: "2026-07-20T06:05:00+00:00",
          receipt_content_sha256: "a".repeat(64),
        },
      ],
    },
    observations: {
      plan_id: PLAN_ID,
      plan_version: 3,
      observations: [
        {
          canonical_gate_id: "M(0,0;1,0)",
          observed_level: null,
          expected_level: 3,
          quality: "unavailable",
          verdict: "unavailable",
          reconciliation_mode: "observe",
          observed_at: "2026-07-20T06:10:00+00:00",
        },
      ],
    },
    executionState: {
      plan_id: PLAN_ID,
      plan_version: 3,
      is_held: true,
      hold_events: [
        { event_type: "held", worker_id: "readback-reconciler", occurred_at: "2026-07-20T06:12:00+00:00" },
      ],
    },
    ...overrides,
  };
}

describe("ControlPlanDetail", () => {
  test("test_dashboard_labels_delivery_as_predicted: never implies observed device state", () => {
    render(<ControlPlanDetail data={data()} />);
    // The header + timeline label the figures as PREDICTED validation, not observed delivery.
    expect(screen.getByText(/PREDICTED, never observed/i)).toBeInTheDocument();
    expect(screen.getByText(/Validated \(predicted\)/)).toBeInTheDocument();
    // It must NOT claim the gate was actually delivered/observed at that level.
    expect(screen.queryByText(/\bdelivered\b/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/observed level/i)).not.toBeInTheDocument();
  });

  test("test_dashboard_shows_unavailable_flume_and_capacity: missing evidence is visible, not masked", () => {
    render(<ControlPlanDetail data={data()} />);
    // A null observed level renders as an explicit dash, NEVER masked to 0.
    expect(screen.getByTestId("observed-level-0")).toHaveTextContent("—");
    expect(screen.getByTestId("observed-level-0")).not.toHaveTextContent("0");
    // The unavailable verdict is shown explicitly.
    expect(screen.getByTestId("verdict-0")).toHaveTextContent(/unavailable/i);
  });

  test("test_dashboard_has_no_command_controls: read-only, no actuation affordance", () => {
    const { container } = render(<ControlPlanDetail data={data()} />);
    expect(container.querySelectorAll("button")).toHaveLength(0);
    expect(container.querySelectorAll("form")).toHaveLength(0);
    expect(container.querySelectorAll("[role='button']")).toHaveLength(0);
    expect(container.querySelectorAll("input")).toHaveLength(0);
  });

  test("shows the derived hold state", () => {
    render(<ControlPlanDetail data={data()} />);
    expect(screen.getByTestId("hold-banner")).toHaveTextContent(/HELD/);
  });

  test("shows the lifecycle state explicitly, flagging a terminal plan as retired", () => {
    render(<ControlPlanDetail data={data({ lifecycleState: "invalidated" })} />);
    const lifecycle = screen.getByTestId("lifecycle-state");
    expect(lifecycle).toHaveTextContent("invalidated");
    expect(lifecycle).toHaveTextContent(/terminal.*retired/i);
    // full plan_id is available via title even though the heading truncates it
    expect(screen.getByRole("heading", { level: 2 })).toHaveAttribute("title", PLAN_ID);
  });

  test("surfaces a STALE badge when the data is stale (last refresh failed)", () => {
    render(<ControlPlanDetail data={data()} stale />);
    expect(screen.getByTestId("stale-badge")).toHaveTextContent(/STALE/);
  });

  test("has no accessibility violations", async () => {
    const { container } = render(<ControlPlanDetail data={data()} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
