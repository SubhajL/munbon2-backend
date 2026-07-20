import Link from "next/link";
import type { ControlPlanSummary } from "@/lib/control-plans-api";

/**
 * Read-only list of shadow control plans. Header-only rows (lifecycle + optimizer/prediction
 * status) linking to the read-only detail view. No approve/activate/cancel affordance — inspection
 * only. `infeasible` / `not_requested` are shown verbatim, never collapsed to a success indicator.
 */
export function ControlPlanList({ plans }: { plans: ControlPlanSummary[] }) {
  if (plans.length === 0) {
    return <p className="text-sm text-fg-muted">No shadow control plans.</p>;
  }
  return (
    <table className="w-full text-sm">
      <caption className="sr-only">Shadow control plans (read-only)</caption>
      <thead>
        <tr className="text-left text-xs text-fg-muted">
          <th scope="col">Plan</th>
          <th scope="col">Lifecycle</th>
          <th scope="col">Optimizer</th>
          <th scope="col">Prediction</th>
          <th scope="col">Trust</th>
        </tr>
      </thead>
      <tbody>
        {plans.map((plan) => (
          <tr key={`${plan.plan_id}:${plan.plan_version}`}>
            <td>
              <Link
                href={`/control-plans/${plan.plan_id}/versions/${plan.plan_version}`}
                className="underline"
              >
                {plan.plan_id.slice(0, 8)}… v{plan.plan_version}
              </Link>
            </td>
            <td data-testid={`lifecycle-${plan.plan_id}`}>{plan.lifecycle_state}</td>
            <td>{plan.optimizer_status}</td>
            <td>{plan.prediction_status}</td>
            <td>{plan.approval_trust ? "trusted" : "untrusted"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
