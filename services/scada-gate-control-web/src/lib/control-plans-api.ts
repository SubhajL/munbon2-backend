/**
 * Read-only client for the water-planning BFF's control-plan projections (PR 6.5c).
 *
 * The operator dashboard inspects the scheduler's NON-COMMANDING shadow plans through the BFF —
 * there is no write/command method here by construction. Types mirror the BFF strict projections
 * (snake_case). Every read is `cache: "no-store"`: control-plane state must never be served stale
 * from a cache (mirrors the BFF's own "must not be cached" rule).
 */
export const BFF_BASE =
  process.env.NEXT_PUBLIC_BFF_BASE_URL ?? "http://localhost:3002";

export type LifecycleState =
  | "draft"
  | "under_review"
  | "approved_for_shadow"
  | "shadow_active"
  | "cancelled"
  | "superseded"
  | "invalidated";

export type ControlPlanSummary = {
  plan_id: string;
  plan_version: number;
  lifecycle_state: LifecycleState;
  approval_trust: boolean;
  optimizer_status: "feasible" | "infeasible";
  prediction_status: "not_requested" | "completed" | "infeasible";
  prediction_run_id: string | null;
  horizon_start: string;
  horizon_end: string;
  created_at: string;
};

export type ControlPlanListPage = {
  items: ControlPlanSummary[];
  next_cursor: string | null;
  projection_schema_version: 1;
};

export type PredictionMemberStatus = {
  member: "lower" | "nominal" | "upper";
  status: "completed" | "infeasible";
};

export type PredictionCoverage = {
  plan_id: string;
  plan_version: number;
  optimizer_status: "feasible" | "infeasible";
  prediction_status: "not_requested" | "completed" | "infeasible";
  prediction_run_id: string | null;
  prediction_member_statuses: PredictionMemberStatus[];
};

export type IntentTimelineEntry = {
  intent_id: string;
  canonical_gate_id: string;
  event_kind: "open" | "trim" | "close";
  event_sequence: number;
  not_before: string;
  deadline: string;
  execution_state: "pending" | "claimed" | "missed" | "invalidated";
  claimed_at: string | null;
  receipt_status: "validation_accepted" | "validation_rejected" | null;
  reason_code: string | null;
  validated_at: string | null;
  dispatched_at: string | null;
  receipt_content_sha256: string | null;
};

export type IntentTimeline = {
  plan_id: string;
  plan_version: number;
  intents: IntentTimelineEntry[];
};

export type ReadbackObservation = {
  canonical_gate_id: string;
  observed_level: number | null;
  expected_level: number;
  quality: string;
  verdict: "ok" | "mismatch" | "unavailable";
  reconciliation_mode: "observe" | "enforce";
  observed_at: string;
};

export type ReadbackObservations = {
  plan_id: string;
  plan_version: number;
  observations: ReadbackObservation[];
};

export type HoldEvent = {
  event_type: "held" | "resumed";
  worker_id: string | null;
  occurred_at: string;
};

export type ExecutionState = {
  plan_id: string;
  plan_version: number;
  is_held: boolean;
  hold_events: HoldEvent[];
};

export class ControlPlanApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ControlPlanApiError";
  }
}

export type LifecycleHistory = {
  plan_id: string;
  plan_version: number;
  lifecycle_state: LifecycleState;
};

export type ControlPlansClientOptions = {
  baseUrl?: string;
  getToken?: () => string | undefined;
  /** Invoked once on a 401 to refresh the token; a returned token triggers a single retry. */
  onUnauthorized?: () => Promise<string | null>;
  fetchImpl?: typeof fetch;
};

export type ControlPlansClient = {
  listControlPlans(cursor?: string, limit?: number): Promise<ControlPlanListPage>;
  getLifecycleHistory(planId: string, version: number): Promise<LifecycleHistory>;
  getPredictionCoverage(planId: string, version: number): Promise<PredictionCoverage>;
  getIntentTimeline(planId: string, version: number): Promise<IntentTimeline>;
  getReadbackObservations(planId: string, version: number): Promise<ReadbackObservations>;
  getExecutionState(planId: string, version: number): Promise<ExecutionState>;
};

export function createControlPlansClient(
  opts: ControlPlansClientOptions = {},
): ControlPlansClient {
  const baseUrl = opts.baseUrl ?? BFF_BASE;
  const doFetch = opts.fetchImpl ?? fetch;

  const send = (path: string, token: string | undefined): Promise<Response> =>
    doFetch(`${baseUrl}${path}`, {
      // Control-plane reads are never cacheable — always the current shadow state.
      cache: "no-store",
      headers: token ? { authorization: `Bearer ${token}` } : {},
    });

  async function getJson<T>(path: string): Promise<T> {
    let res = await send(path, opts.getToken?.());
    // On a 401 (expired in-memory token), refresh ONCE and retry — otherwise a long-open
    // polling dashboard would break permanently at token expiry.
    if (res.status === 401 && opts.onUnauthorized) {
      const refreshed = await opts.onUnauthorized();
      if (refreshed) res = await send(path, refreshed);
    }
    if (!res.ok) {
      throw new ControlPlanApiError(`GET ${path} failed (${res.status})`, res.status);
    }
    return (await res.json()) as T;
  }

  const versioned = (planId: string, version: number, suffix: string): string =>
    `/api/v1/control-plans/${encodeURIComponent(planId)}/versions/${version}${suffix}`;

  return {
    listControlPlans: (cursor, limit = 25) => {
      const params = new URLSearchParams({ limit: String(limit) });
      if (cursor) params.set("cursor", cursor);
      return getJson<ControlPlanListPage>(`/api/v1/control-plans?${params.toString()}`);
    },
    getLifecycleHistory: (planId, version) =>
      getJson<LifecycleHistory>(versioned(planId, version, "/lifecycle-history")),
    getPredictionCoverage: (planId, version) =>
      getJson<PredictionCoverage>(versioned(planId, version, "/prediction-coverage")),
    getIntentTimeline: (planId, version) =>
      getJson<IntentTimeline>(versioned(planId, version, "/intent-timeline")),
    getReadbackObservations: (planId, version) =>
      getJson<ReadbackObservations>(versioned(planId, version, "/readback-observations")),
    getExecutionState: (planId, version) =>
      getJson<ExecutionState>(versioned(planId, version, "/execution-state")),
  };
}
