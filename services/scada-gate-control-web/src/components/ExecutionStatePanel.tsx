import type { ExecutionState } from "@/lib/control-plans-api";

/**
 * Read-only plan-level execution posture: the derived hold banner + the held/resumed history.
 * A hold pauses claiming without releasing authority — it is NOT a lifecycle exit. No resume/hold
 * control is offered here (read-only dashboard).
 */
export function ExecutionStatePanel({ state }: { state: ExecutionState }) {
  return (
    <section aria-labelledby="execution-heading">
      <h3 id="execution-heading" className="text-sm font-medium">
        Execution state
      </h3>
      <p data-testid="hold-banner" className="mt-1 text-sm">
        {state.is_held ? "HELD — claiming paused" : "Active — not held"}
      </p>
      {state.hold_events.length > 0 && (
        <ul className="mt-1 text-xs text-fg-muted">
          {state.hold_events.map((event, index) => (
            <li key={index}>
              {event.event_type} · {event.worker_id ?? "unknown"} · {event.occurred_at}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
