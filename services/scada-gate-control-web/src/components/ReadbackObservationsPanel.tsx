import type { ReadbackObservation } from "@/lib/control-plans-api";

/**
 * Read-only shadow readback observations. Missing evidence is shown EXPLICITLY: an `unavailable`
 * verdict and a null observed level render as "unavailable" / "—", NEVER masked to 0 or hidden —
 * the operator must be able to see that flume/capacity evidence is missing, not fabricated.
 */
export function ReadbackObservationsPanel({
  observations,
}: {
  observations: ReadbackObservation[];
}) {
  if (observations.length === 0) {
    return (
      <p className="text-sm text-fg-muted">
        No readback observations (reconciliation dark or no evidence yet).
      </p>
    );
  }
  return (
    <table className="w-full text-sm">
      <caption className="sr-only">Shadow readback observations</caption>
      <thead>
        <tr className="text-left text-xs text-fg-muted">
          <th scope="col">Gate</th>
          <th scope="col">Readback level</th>
          <th scope="col">Expected level</th>
          <th scope="col">Verdict</th>
        </tr>
      </thead>
      <tbody>
        {observations.map((obs, index) => (
          <tr key={`${obs.canonical_gate_id}-${index}`} data-testid={`observation-${index}`}>
            <td>{obs.canonical_gate_id}</td>
            <td data-testid={`observed-level-${index}`}>
              {/* `== null` also catches an absent (drift/undefined) field so it renders "—",
                  never a blank cell — missing evidence must stay visible. */}
              {obs.observed_level == null ? "—" : obs.observed_level}
            </td>
            <td>{obs.expected_level}</td>
            <td data-testid={`verdict-${index}`}>
              {obs.verdict === "unavailable"
                ? "unavailable (evidence missing)"
                : obs.verdict}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
