"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { usePolling } from "@/hooks/usePolling";
import { useAuth } from "@/components/AuthProvider";
import { RequireAuth } from "@/components/RequireAuth";
import {
  ControlPlanDetail,
  type ControlPlanDetailData,
} from "@/components/ControlPlanDetail";
import {
  ControlAuthorityPanel,
} from "@/components/ControlAuthorityPanel";
import type { AuthorityActionSubmission } from "@/components/AuthorityActionDialog";
import {
  createControlAuthorityClient,
} from "@/lib/control-authority-api";
import type { ControlAuthorityDashboard } from "@/lib/control-authority-proxy";
import {
  createControlPlansClient,
  type ExecutionState,
} from "@/lib/control-plans-api";

const POLL_MS = 5000;
type PlanProjectionData = Omit<ControlPlanDetailData, "executionState">;
type AuthorityProjectionData = {
  authority: ControlAuthorityDashboard;
  executionState: ExecutionState;
};

export default function ControlPlanDetailPage() {
  const params = useParams<{ planId: string; version: string }>();
  const version = Number(params.version);
  return (
    <RequireAuth>
      {/* key on the route so a client-side navigation to another plan RESETS the poll state —
          otherwise the previous plan's data would show under the new URL until the next tick. */}
      <DetailContent key={`${params.planId}:${params.version}`} planId={params.planId} version={version} />
    </RequireAuth>
  );
}

function DetailContent({ planId, version }: { planId: string; version: number }) {
  const { getToken, refresh, session } = useAuth();
  const [mutationPending, setMutationPending] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const client = useMemo(
    () => createControlPlansClient({ getToken, onUnauthorized: refresh }),
    [getToken, refresh],
  );
  const authorityClient = useMemo(
    () => createControlAuthorityClient({ getToken, onUnauthorized: refresh }),
    [getToken, refresh],
  );

  const planPoll = usePolling<PlanProjectionData>(async () => {
    const [history, coverage, timeline, observations] = await Promise.all([
      client.getLifecycleHistory(planId, version),
      client.getPredictionCoverage(planId, version),
      client.getIntentTimeline(planId, version),
      client.getReadbackObservations(planId, version),
    ]);
    return {
      planId,
      planVersion: version,
      lifecycleState: history.lifecycle_state,
      coverage,
      timeline,
      observations,
    };
  }, POLL_MS, Number.isFinite(version));
  const authorityPoll = usePolling<AuthorityProjectionData>(async () => {
    const [authority, executionState] = await Promise.all([
      authorityClient.read(planId, version),
      client.getExecutionState(planId, version),
    ]);
    return { authority, executionState };
  }, POLL_MS, Number.isFinite(version));

  const handleAction = async (submission: AuthorityActionSubmission): Promise<void> => {
    setMutationPending(true);
    setMutationError(null);
    try {
      await authorityClient.mutate(
        submission.mutation,
        submission.confirmation,
        submission.stepUpCode,
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "Authority action failed";
      setMutationError(message);
      throw error;
    } finally {
      setMutationPending(false);
    }
  };

  return (
    <main className="p-4">
      <h1 className="text-lg font-semibold">Shadow control plan</h1>
      {!Number.isFinite(version) && (
        <p role="alert" className="text-sm" style={{ color: "var(--color-offline)" }}>
          Invalid plan version.
        </p>
      )}
      {planPoll.error && (
        <p role="alert" className="mt-1 text-sm" style={{ color: "var(--color-offline)" }}>
          {planPoll.data
            ? "Last refresh failed — the figures below may be STALE."
            : `Failed to load shadow plan: ${planPoll.error.message}`}
        </p>
      )}
      {authorityPoll.error && !authorityPoll.data && (
        <p role="alert" className="mt-1 text-sm" style={{ color: "var(--color-offline)" }}>
          Failed to load execution authority: {authorityPoll.error.message}
        </p>
      )}
      {planPoll.loading && !planPoll.data && (
        <p role="status" className="mt-1 text-sm text-fg-muted">
          Loading shadow plan…
        </p>
      )}
      {planPoll.data && authorityPoll.data && (
        <div
          className="mt-3"
          aria-busy={planPoll.error || authorityPoll.error ? true : undefined}
          data-stale={planPoll.error || authorityPoll.error ? "true" : undefined}
        >
          <ControlPlanDetail
            data={{
              ...planPoll.data,
              executionState: authorityPoll.data.executionState,
            }}
            stale={planPoll.error !== null || authorityPoll.error !== null}
          />
        </div>
      )}
      {authorityPoll.data && (
        <div className="mt-4">
          <ControlAuthorityPanel
            dashboard={authorityPoll.data.authority}
            role={session?.user.role ?? "viewer"}
            isHeld={authorityPoll.data.executionState.is_held}
            stale={authorityPoll.error !== null}
            pending={mutationPending}
            error={mutationError}
            onAction={handleAction}
          />
        </div>
      )}
    </main>
  );
}
