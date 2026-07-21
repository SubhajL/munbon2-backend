"use client";

import { useState } from "react";
import type { AppRole } from "@/lib/role";
import type {
  ControlAuthorityDashboard,
  MutationAction,
} from "@/lib/control-authority-proxy";
import {
  AuthorityActionDialog,
  type AuthorityActionSubmission,
} from "./AuthorityActionDialog";

type Props = {
  dashboard: ControlAuthorityDashboard;
  role: AppRole;
  isHeld: boolean;
  stale: boolean;
  pending: boolean;
  error?: string | null;
  onAction: (submission: AuthorityActionSubmission) => Promise<void> | void;
};

const shortHash = (value: string): string => `${value.slice(0, 10)}…`;

export function ControlAuthorityPanel({
  dashboard,
  role,
  isHeld,
  stale,
  pending,
  error,
  onAction,
}: Props) {
  const [selected, setSelected] = useState<MutationAction | null>(null);
  const { applicability, grant, scada } = dashboard;
  const canManage = role === "admin";
  const machineReady = scada.available && scada.healthy && scada.matches_scheduler;
  const actionButton = (
    action: MutationAction,
    label: string,
    needsMachine = false,
    safetyBrake = false,
  ) => (
    <button
      type="button"
      onClick={() => setSelected(action)}
      disabled={
        pending ||
        (!safetyBrake && (stale || (needsMachine && !machineReady)))
      }
      className="rounded border border-border px-3 py-2 text-xs font-semibold disabled:opacity-50"
    >
      {label}
    </button>
  );

  return (
    <section aria-labelledby="authority-heading" className="space-y-3 rounded-xl border border-border p-4">
      <header>
        <h3 id="authority-heading" className="text-sm font-semibold">
          Execution authority
        </h3>
        <p className="text-xs text-fg-muted">
          Evidence and authority only. This panel has no device command path.
        </p>
      </header>
      {stale && (
        <p role="status" className="text-xs font-semibold text-red-600">
          STALE — positive actions are disabled until a complete refresh.
          Hold and revoke remain available as safety brakes.
        </p>
      )}
      <dl className="grid gap-2 text-xs sm:grid-cols-2">
        <div>
          <dt className="text-fg-muted">Model release</dt>
          <dd>{applicability.model_release_id}</dd>
          <dd className="font-mono">{shortHash(applicability.model_release_content_hash)}</dd>
          <dd className="font-mono">engine {shortHash(applicability.engine_descriptor_content_hash)}</dd>
        </div>
        <div>
          <dt className="text-fg-muted">Capability</dt>
          <dd>{applicability.capability_release_id}</dd>
          <dd className="font-mono">{shortHash(applicability.capability_hash)}</dd>
          <dd>{machineReady ? "Scheduler and live SCADA match" : "SCADA unavailable or capability mismatch"}</dd>
        </div>
        <div>
          <dt className="text-fg-muted">Accepted matching receipts</dt>
          <dd>
            {applicability.matching_receipt_intent_count} / {applicability.outbox_intent_count}
          </dd>
        </div>
        <div>
          <dt className="text-fg-muted">Physical scope</dt>
          <dd>{applicability.scope.gate_paths.map((path) => `${path.section_id}:${path.canonical_gate_id}`).join(", ") || "None"}</dd>
        </div>
      </dl>
      {applicability.blockers.length > 0 && (
        <div>
          <h4 className="text-xs font-medium">Grant blockers</h4>
          <ul className="list-disc pl-5 text-xs">
            {applicability.blockers.map((blocker) => (
              <li key={blocker}>{blocker}</li>
            ))}
          </ul>
        </div>
      )}
      {grant && (
        <div className="text-xs">
          <p>
            Grant {grant.grant_id} — <strong>{grant.status}</strong>, expires {grant.effective_expires_at}
          </p>
          <ol className="mt-1 list-decimal pl-5">
            {grant.events.map((event) => (
              <li key={event.event_sequence}>
                {event.event_type} by {event.actor_subject}: {event.reason}
              </li>
            ))}
          </ol>
        </div>
      )}
      {canManage && (
        <div className="flex flex-wrap gap-2" aria-label="Authority actions">
          {applicability.lifecycle_state === "under_review" && actionButton("approve-shadow", "Approve for shadow")}
          {applicability.lifecycle_state === "approved_for_shadow" && actionButton("activate", "Activate shadow", true)}
          {applicability.lifecycle_state === "shadow_active" &&
            (isHeld
              ? actionButton("resume", "Resume plan", true)
              : actionButton("hold", "Hold plan", false, true))}
          {applicability.can_grant && actionButton("grant", "Grant authority", true)}
          {grant?.status === "active" && actionButton("renew", "Renew authority", true)}
          {grant &&
            grant.status !== "revoked" &&
            actionButton("revoke", "Revoke authority", false, true)}
        </div>
      )}
      <aside className="rounded border border-amber-500/50 p-3 text-xs">
        Emergency handoff: place the plan on hold, revoke execution authority,
        then follow the field manual-control procedure. This UI never performs
        a machine write.
      </aside>
      {selected && (
        <AuthorityActionDialog
          key={selected}
          open
          action={selected}
          planId={applicability.plan_id}
          planVersion={applicability.plan_version}
          grantId={grant?.grant_id}
          pending={pending}
          error={error}
          onCancel={() => setSelected(null)}
          onSubmit={(submission) => {
            void Promise.resolve(onAction(submission))
              .then(() => setSelected(null))
              .catch(() => undefined);
          }}
        />
      )}
    </section>
  );
}
