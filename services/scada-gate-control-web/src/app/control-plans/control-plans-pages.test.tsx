import { render } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

// The pages are where a Server Action / mutation button would most naturally be added, so guard
// them directly: neither route may render ANY command affordance (the dashboard never actuates).
const h = vi.hoisted(() => ({
  state: { data: null as unknown, error: null as Error | null, loading: false },
}));

vi.mock("@/hooks/usePolling", () => ({ usePolling: () => h.state }));
vi.mock("@/components/RequireAuth", () => ({
  RequireAuth: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
vi.mock("@/components/AuthProvider", () => ({
  useAuth: () => ({ getToken: () => "t", refresh: async () => null }),
}));
vi.mock("next/navigation", () => ({
  useParams: () => ({ planId: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", version: "3" }),
}));

import ControlPlansPage from "./page";
import ControlPlanDetailPage from "./[planId]/versions/[version]/page";

const PLAN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

function assertNoCommandControls(container: HTMLElement) {
  expect(
    container.querySelectorAll("button, form, input, select, textarea, [role='button']"),
  ).toHaveLength(0);
}

describe("control-plan pages are read-only", () => {
  test("the list page renders no command controls", () => {
    h.state = {
      data: {
        items: [
          {
            plan_id: PLAN_ID,
            plan_version: 3,
            lifecycle_state: "shadow_active",
            approval_trust: true,
            optimizer_status: "feasible",
            prediction_status: "completed",
            prediction_run_id: null,
            horizon_start: "2026-07-20T00:00:00+00:00",
            horizon_end: "2026-07-21T00:00:00+00:00",
            created_at: "2026-07-19T20:00:00+00:00",
          },
        ],
        next_cursor: null,
      },
      error: null,
      loading: false,
    };
    const { container } = render(<ControlPlansPage />);
    assertNoCommandControls(container);
  });

  test("the detail page renders no command controls", () => {
    h.state = {
      data: {
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
        executionState: { plan_id: PLAN_ID, plan_version: 3, is_held: false, hold_events: [] },
      },
      error: null,
      loading: false,
    };
    const { container } = render(<ControlPlanDetailPage />);
    assertNoCommandControls(container);
  });
});
