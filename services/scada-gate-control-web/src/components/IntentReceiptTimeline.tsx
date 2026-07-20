import type { IntentTimelineEntry } from "@/lib/control-plans-api";

/**
 * Read-only per-intent claimed→dispatched→validated timeline. Every row is PREDICTED command
 * evidence from a shadow plan — the receipt is a VALIDATION receipt (the machine boundary
 * validated the intent), NOT a confirmation the gate moved. Nothing here implies observed device
 * state, and there is no command affordance.
 */
const RECEIPT_LABEL: Record<string, string> = {
  validation_accepted: "Validated (predicted)",
  validation_rejected: "Rejected",
};

export function IntentReceiptTimeline({ intents }: { intents: IntentTimelineEntry[] }) {
  if (intents.length === 0) {
    return <p className="text-sm text-fg-muted">No command intents in this shadow plan.</p>;
  }
  return (
    <table className="w-full text-sm">
      <caption className="sr-only">
        Predicted command-intent timeline (validation only — never observed gate state)
      </caption>
      <thead>
        <tr className="text-left text-xs text-fg-muted">
          <th scope="col">Gate</th>
          <th scope="col">Action</th>
          <th scope="col">Execution</th>
          <th scope="col">Predicted validation</th>
          <th scope="col">Reason</th>
        </tr>
      </thead>
      <tbody>
        {intents.map((intent) => (
          <tr key={intent.intent_id} data-testid={`intent-${intent.event_sequence}`}>
            <td>{intent.canonical_gate_id}</td>
            <td>{intent.event_kind}</td>
            <td>{intent.execution_state}</td>
            <td>
              {intent.receipt_status
                ? RECEIPT_LABEL[intent.receipt_status] ?? intent.receipt_status
                : intent.dispatched_at
                  ? "Awaiting validation receipt"
                  : "Not yet dispatched"}
            </td>
            <td>{intent.reason_code ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
