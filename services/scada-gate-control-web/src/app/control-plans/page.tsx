"use client";

import { useMemo } from "react";
import { usePolling } from "@/hooks/usePolling";
import { useAuth } from "@/components/AuthProvider";
import { RequireAuth } from "@/components/RequireAuth";
import { ControlPlanList } from "@/components/ControlPlanList";
import { createControlPlansClient } from "@/lib/control-plans-api";

const POLL_MS = 5000;

export default function ControlPlansPage() {
  return (
    <RequireAuth>
      <ControlPlansContent />
    </RequireAuth>
  );
}

function ControlPlansContent() {
  const { getToken, refresh } = useAuth();
  const client = useMemo(
    () => createControlPlansClient({ getToken, onUnauthorized: refresh }),
    [getToken, refresh],
  );
  const poll = usePolling(() => client.listControlPlans(), POLL_MS);

  return (
    <main className="p-4">
      <h1 className="text-lg font-semibold">Shadow control plans</h1>
      <p className="text-xs text-fg-muted">
        Read-only inspection of the scheduler&apos;s non-commanding shadow plans.
      </p>
      {poll.error && (
        <p role="alert" className="mt-2 text-sm" style={{ color: "var(--color-offline)" }}>
          {poll.data
            ? "Last refresh failed — the list below may be STALE."
            : `Failed to load control plans: ${poll.error.message}`}
        </p>
      )}
      {poll.loading && !poll.data && (
        <p role="status" className="mt-2 text-sm text-fg-muted">
          Loading control plans…
        </p>
      )}
      {poll.data && (
        <div className="mt-3">
          <ControlPlanList plans={poll.data.items} />
          {poll.data.next_cursor && (
            <p className="mt-2 text-xs text-fg-muted">
              Showing the most recent page — more shadow plans exist beyond this page.
            </p>
          )}
        </div>
      )}
    </main>
  );
}
