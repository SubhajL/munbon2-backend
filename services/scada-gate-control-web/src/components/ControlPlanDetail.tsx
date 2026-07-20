import type {
  ExecutionState,
  IntentTimeline,
  LifecycleState,
  PredictionCoverage,
  ReadbackObservations,
} from "@/lib/control-plans-api";
import { ExecutionStatePanel } from "./ExecutionStatePanel";
import { IntentReceiptTimeline } from "./IntentReceiptTimeline";
import { PredictionCoveragePanel } from "./PredictionCoveragePanel";
import { ReadbackObservationsPanel } from "./ReadbackObservationsPanel";

export type ControlPlanDetailData = {
  planId: string;
  planVersion: number;
  lifecycleState: LifecycleState;
  coverage: PredictionCoverage;
  timeline: IntentTimeline;
  observations: ReadbackObservations;
  executionState: ExecutionState;
};

const TERMINAL_STATES: readonly LifecycleState[] = ["cancelled", "superseded", "invalidated"];

/**
 * Read-only shadow-plan detail: the plan's lifecycle state, prediction coverage, the predicted
 * intent/receipt timeline, shadow readback observations, and the execution/hold state. Composed of
 * prop-driven panels; there is NO command control anywhere on this page (inspection only).
 */
export function ControlPlanDetail({
  data,
  stale = false,
}: {
  data: ControlPlanDetailData;
  stale?: boolean;
}) {
  const isTerminal = TERMINAL_STATES.includes(data.lifecycleState);
  return (
    <article aria-labelledby="plan-heading" className="space-y-4">
      <header>
        <h2 id="plan-heading" className="text-base font-semibold" title={data.planId}>
          Shadow plan {data.planId.slice(0, 8)}… v{data.planVersion}
        </h2>
        {/* Lifecycle is shown EXPLICITLY so a cancelled/invalidated plan is never read as live. */}
        <p data-testid="lifecycle-state" className="text-sm">
          Lifecycle: <span className={isTerminal ? "font-semibold" : ""}>{data.lifecycleState}</span>
          {isTerminal ? " (terminal — this plan is retired)" : ""}
        </p>
        {stale && (
          <p data-testid="stale-badge" role="status" className="text-xs font-semibold" style={{ color: "var(--color-offline)" }}>
            STALE — the last refresh failed; these figures may be out of date.
          </p>
        )}
        <p className="text-xs text-fg-muted">
          Read-only inspection — delivery figures are PREDICTED, never observed device state.
        </p>
      </header>

      <PredictionCoveragePanel coverage={data.coverage} />

      <section aria-labelledby="timeline-heading">
        <h3 id="timeline-heading" className="text-sm font-medium">
          Predicted command timeline
        </h3>
        <IntentReceiptTimeline intents={data.timeline.intents} />
      </section>

      <section aria-labelledby="readback-heading">
        <h3 id="readback-heading" className="text-sm font-medium">
          Shadow readback
        </h3>
        <ReadbackObservationsPanel observations={data.observations.observations} />
      </section>

      <ExecutionStatePanel state={data.executionState} />
    </article>
  );
}
