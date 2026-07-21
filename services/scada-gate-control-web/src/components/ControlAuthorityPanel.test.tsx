import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import type { ControlAuthorityDashboard } from "@/lib/control-authority-proxy";
import { ControlAuthorityPanel } from "./ControlAuthorityPanel";

const PLAN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const GRANT_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";

function dashboard(
  overrides: Partial<ControlAuthorityDashboard> = {},
): ControlAuthorityDashboard {
  const base: ControlAuthorityDashboard = {
    applicability: {
      plan_id: PLAN_ID,
      plan_version: 3,
      evaluated_at: "2026-07-21T02:00:00Z",
      lifecycle_state: "shadow_active",
      model_release_id: "model-r1",
      model_release_content_hash: "a".repeat(64),
      engine_descriptor_content_hash: "b".repeat(64),
      model_release_commandable: true,
      capability_release_id: "cap-r1",
      capability_hash: "c".repeat(64),
      capability_configured: true,
      capability_matches_outbox: true,
      scope: {
        schema_version: 1,
        gate_paths: [
          {
            section_id: "S1",
            canonical_gate_id: "G1",
            path_reach_ids: ["R1"],
          },
        ],
      },
      flow_lower_exclusive_m3s: 0,
      flow_upper_inclusive_m3s: 5,
      initialization: { kind: "dry" },
      maximum_continuous_open_seconds: 3600,
      maximum_intermediate_trims: 1,
      outbox_intent_count: 2,
      accepted_receipt_intent_count: 2,
      matching_receipt_intent_count: 2,
      receipt_coverage_complete: true,
      existing_grant_status: "active",
      existing_grant_id: GRANT_ID,
      blockers: ["grant_already_exists"],
      can_grant: false,
    },
    grant: {
      grant_id: GRANT_ID,
      plan_id: PLAN_ID,
      plan_version: 3,
      status: "active",
      effective_expires_at: "2026-07-21T12:00:00Z",
      model_release_id: "model-r1",
      model_release_content_hash: "a".repeat(64),
      engine_descriptor_content_hash: "b".repeat(64),
      capability_release_id: "cap-r1",
      capability_hash: "c".repeat(64),
      grant_content_sha256: "d".repeat(64),
      events: [
        {
          event_sequence: 1,
          event_type: "granted",
          effective_expires_at: "2026-07-21T12:00:00Z",
          actor_subject: "admin-1",
          reason: "pilot",
          occurred_at: "2026-07-21T02:00:00Z",
        },
      ],
    },
    scada: {
      available: true,
      healthy: true,
      capability_release_id: "cap-r1",
      capability_hash: "c".repeat(64),
      matches_scheduler: true,
    },
  };
  return { ...base, ...overrides };
}

describe("ControlAuthorityPanel", () => {
  test("viewer sees authority evidence but zero controls", () => {
    const { container } = render(
      <ControlAuthorityPanel
        dashboard={dashboard()}
        role="viewer"
        isHeld={false}
        stale={false}
        pending={false}
        onAction={vi.fn()}
      />,
    );

    expect(screen.getByText(/model-r1/)).toBeInTheDocument();
    expect(screen.getByText(/2 \/ 2/)).toBeInTheDocument();
    expect(container.querySelectorAll("button")).toHaveLength(0);
    expect(container.querySelectorAll("form")).toHaveLength(0);
  });

  test("SCADA outage disables positive action but leaves hold and revoke available", () => {
    render(
      <ControlAuthorityPanel
        dashboard={dashboard({
          scada: {
            available: false,
            healthy: false,
            capability_release_id: null,
            capability_hash: null,
            matches_scheduler: false,
          },
        })}
        role="admin"
        isHeld={false}
        stale={false}
        pending={false}
        onAction={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: /renew authority/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /hold plan/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /revoke authority/i })).toBeEnabled();
  });

  test("stale dashboard disables positive actions but preserves the safety brakes", () => {
    render(
      <ControlAuthorityPanel
        dashboard={dashboard()}
        role="admin"
        isHeld={false}
        stale
        pending={false}
        onAction={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /renew authority/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /hold plan/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /revoke authority/i })).toBeEnabled();
  });
});
