"use client";

import { useMemo } from "react";
import { useParams } from "next/navigation";
import { usePolling } from "@/hooks/usePolling";
import { useAuth } from "@/components/AuthProvider";
import { RequireAuth } from "@/components/RequireAuth";
import {
  ControlPlanDetail,
  type ControlPlanDetailData,
} from "@/components/ControlPlanDetail";
import { createControlPlansClient } from "@/lib/control-plans-api";

const POLL_MS = 5000;

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
  const { getToken, refresh } = useAuth();
  const client = useMemo(
    () => createControlPlansClient({ getToken, onUnauthorized: refresh }),
    [getToken, refresh],
  );

  const poll = usePolling<ControlPlanDetailData>(async () => {
    // All five reads key on the same plan-existence check, so they succeed or 404 TOGETHER —
    // a single-read 404 for an existing plan is unreachable, so Promise.all is correct here.
    const [history, coverage, timeline, observations, executionState] = await Promise.all([
      client.getLifecycleHistory(planId, version),
      client.getPredictionCoverage(planId, version),
      client.getIntentTimeline(planId, version),
      client.getReadbackObservations(planId, version),
      client.getExecutionState(planId, version),
    ]);
    return {
      planId,
      planVersion: version,
      lifecycleState: history.lifecycle_state,
      coverage,
      timeline,
      observations,
      executionState,
    };
  }, POLL_MS, Number.isFinite(version));

  return (
    <main className="p-4">
      <h1 className="text-lg font-semibold">Shadow control plan</h1>
      {!Number.isFinite(version) && (
        <p role="alert" className="text-sm" style={{ color: "var(--color-offline)" }}>
          Invalid plan version.
        </p>
      )}
      {poll.error && (
        <p role="alert" className="mt-1 text-sm" style={{ color: "var(--color-offline)" }}>
          {poll.data
            ? "Last refresh failed — the figures below may be STALE."
            : `Failed to load shadow plan: ${poll.error.message}`}
        </p>
      )}
      {poll.loading && !poll.data && (
        <p role="status" className="mt-1 text-sm text-fg-muted">
          Loading shadow plan…
        </p>
      )}
      {poll.data && (
        <div className="mt-3" aria-busy={poll.error ? true : undefined} data-stale={poll.error ? "true" : undefined}>
          <ControlPlanDetail data={poll.data} stale={poll.error !== null} />
        </div>
      )}
    </main>
  );
}
