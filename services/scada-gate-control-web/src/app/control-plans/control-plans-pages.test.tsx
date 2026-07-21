import { render } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

// The plan list remains read-only. The detail route may render authority and lifecycle controls
// for admins, but never a device-command affordance; viewers still receive a read-only projection.
const h = vi.hoisted(() => ({
  states: [] as Array<{
    data: unknown;
    error: Error | null;
    loading: boolean;
  }>,
  call: 0,
  role: "viewer" as "viewer" | "admin",
}));

vi.mock("@/hooks/usePolling", () => ({
  usePolling: () => h.states[h.call++],
}));
vi.mock("@/components/RequireAuth", () => ({
  RequireAuth: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
vi.mock("@/components/AuthProvider", () => ({
  useAuth: () => ({
    getToken: () => "t",
    refresh: async () => null,
    session: { user: { email: "viewer@example.test", role: h.role } },
  }),
}));
vi.mock("next/navigation", () => ({
  useParams: () => ({ planId: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", version: "3" }),
}));

import ControlPlansPage from "./page";
import ControlPlanDetailPage from "./[planId]/versions/[version]/page";

const PLAN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const executionState = {
  plan_id: PLAN_ID,
  plan_version: 3,
  is_held: false,
  hold_events: [],
};
const authority = {
  applicability: {
    plan_id: PLAN_ID,
    plan_version: 3,
    evaluated_at: "2026-07-21T02:00:00Z",
    lifecycle_state: "shadow_active",
    model_release_id: "model-r1",
    model_release_content_hash: "a".repeat(64),
    engine_descriptor_content_hash: "b".repeat(64),
    model_release_commandable: false,
    capability_release_id: "unconfigured",
    capability_hash: "0".repeat(64),
    capability_configured: false,
    capability_matches_outbox: false,
    scope: { schema_version: 1, gate_paths: [] },
    flow_lower_exclusive_m3s: 0,
    flow_upper_inclusive_m3s: 0,
    initialization: { kind: "dry" },
    maximum_continuous_open_seconds: 1,
    maximum_intermediate_trims: 0,
    outbox_intent_count: 0,
    accepted_receipt_intent_count: 0,
    matching_receipt_intent_count: 0,
    receipt_coverage_complete: false,
    existing_grant_status: null,
    existing_grant_id: null,
    blockers: ["noncommandable_release", "capability_unconfigured"],
    can_grant: false,
  },
  grant: null,
  scada: {
    available: false,
    healthy: false,
    capability_release_id: null,
    capability_hash: null,
    matches_scheduler: false,
  },
};

const planDetail = {
  planId: PLAN_ID,
  planVersion: 3,
  lifecycleState: "shadow_active",
  coverage: {
    plan_id: PLAN_ID,
    plan_version: 3,
    optimizer_status: "feasible",
    prediction_status: "completed",
    prediction_run_id: null,
    prediction_member_statuses: [],
  },
  timeline: { plan_id: PLAN_ID, plan_version: 3, intents: [] },
  observations: { plan_id: PLAN_ID, plan_version: 3, observations: [] },
};

function assertNoCommandControls(container: HTMLElement) {
  expect(
    container.querySelectorAll("button, form, input, select, textarea, [role='button']"),
  ).toHaveLength(0);
}

describe("control-plan page authority boundaries", () => {
  test("the list page renders no command controls", () => {
    h.call = 0;
    h.role = "viewer";
    h.states = [{
      data: {
        items: [
          {
            plan_id: PLAN_ID,
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
            prediction_run_id: null,
            prediction_response_sha256: null,
            created_by_subject: "operator-7",
            horizon_start: "2026-07-20T00:00:00+00:00",
            horizon_end: "2026-07-21T00:00:00+00:00",
            created_at: "2026-07-19T20:00:00+00:00",
          },
        ],
        next_cursor: null,
      },
      error: null,
      loading: false,
    }];
    const { container } = render(<ControlPlansPage />);
    assertNoCommandControls(container);
  });

  test("the detail page renders authority evidence but no controls for a viewer", () => {
    h.call = 0;
    h.role = "viewer";
    h.states = [
      { data: planDetail, error: null, loading: false },
      { data: { authority, executionState }, error: null, loading: false },
    ];
    const { container } = render(<ControlPlanDetailPage />);
    expect(container).toHaveTextContent("Execution authority");
    expect(container).toHaveTextContent("noncommandable_release");
    assertNoCommandControls(container);
  });

  test("an informational projection failure does not remove hold and revoke", () => {
    h.call = 0;
    h.role = "admin";
    h.states = [
      { data: null, error: new Error("readback unavailable"), loading: false },
      { data: { authority: { ...authority, grant: {
        grant_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        plan_id: PLAN_ID,
        plan_version: 3,
        status: "active",
        effective_expires_at: "2026-07-21T12:00:00Z",
        model_release_id: "model-r1",
        model_release_content_hash: "a".repeat(64),
        engine_descriptor_content_hash: "b".repeat(64),
        capability_release_id: "unconfigured",
        capability_hash: "0".repeat(64),
        grant_content_sha256: "d".repeat(64),
        events: [{
          event_sequence: 1,
          event_type: "granted",
          effective_expires_at: "2026-07-21T12:00:00Z",
          actor_subject: "admin-1",
          reason: "pilot",
          occurred_at: "2026-07-21T02:00:00Z",
        }],
      } }, executionState }, error: null, loading: false },
    ];

    const { getByRole } = render(<ControlPlanDetailPage />);

    expect(getByRole("button", { name: /hold plan/i })).toBeEnabled();
    expect(getByRole("button", { name: /revoke authority/i })).toBeEnabled();
  });
});
