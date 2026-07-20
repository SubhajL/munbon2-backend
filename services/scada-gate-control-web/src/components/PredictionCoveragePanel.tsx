import type { PredictionCoverage } from "@/lib/control-plans-api";

/**
 * Read-only prediction coverage. Preserves the scheduler's exact status vocabulary
 * (`not_requested` / `completed` / `infeasible`) verbatim — NO success percentages, no zero-count
 * fabrication. `infeasible`/`not_requested` are shown explicitly as missing/incomplete evidence.
 */
const PREDICTION_LABEL: Record<string, string> = {
  not_requested: "Not requested (no prediction)",
  completed: "Completed",
  infeasible: "Infeasible",
};

export function PredictionCoveragePanel({ coverage }: { coverage: PredictionCoverage }) {
  return (
    <section aria-labelledby="coverage-heading">
      <h3 id="coverage-heading" className="text-sm font-medium">
        Prediction coverage
      </h3>
      <dl className="mt-1 text-sm">
        <div className="flex gap-2">
          <dt className="text-fg-muted">Optimizer</dt>
          <dd>{coverage.optimizer_status}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="text-fg-muted">Prediction</dt>
          <dd data-testid="prediction-status">
            {PREDICTION_LABEL[coverage.prediction_status] ?? coverage.prediction_status}
          </dd>
        </div>
      </dl>
      <ul className="mt-1 text-sm">
        {coverage.prediction_member_statuses.map((member) => (
          <li key={member.member} data-testid={`member-${member.member}`}>
            {member.member}: {member.status}
          </li>
        ))}
      </ul>
    </section>
  );
}
