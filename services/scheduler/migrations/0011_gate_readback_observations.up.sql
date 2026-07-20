-- 0011_gate_readback_observations (PR 6.3b)
-- Append-only audit of shadow readback reconciliation: one row per (plan, gate) reconcile,
-- recording the observed vs expected(baseline) level, the reading quality, the verdict, and the
-- mode it ran in. This is the durable evidence behind a hold-on-drift decision; the hold itself
-- is a plan-level 'held' execution event (0009). Purely additive; reuses the 0001 immutability
-- trigger. Canonical documents are TEXT (there are none here — all typed columns). NOTHING here
-- actuates. `off` mode never records (no reconciliation runs), so the mode CHECK is observe|enforce.

CREATE TABLE scheduler.control_gate_readback_observations (
    observation_id UUID NOT NULL,
    plan_id UUID NOT NULL,
    plan_version INTEGER NOT NULL,
    canonical_gate_id TEXT NOT NULL,
    observed_level INTEGER,
    expected_level INTEGER NOT NULL,
    quality TEXT NOT NULL,
    verdict TEXT NOT NULL,
    reconciliation_mode TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT control_gate_readback_observations_pkey PRIMARY KEY (observation_id),
    CONSTRAINT control_gate_readback_observations_run_fkey
        FOREIGN KEY (plan_id, plan_version)
        REFERENCES scheduler.control_plan_runs (plan_id, plan_version)
        ON DELETE RESTRICT,
    CONSTRAINT control_gate_readback_observations_verdict
        CHECK (verdict IN ('ok', 'mismatch', 'unavailable')),
    CONSTRAINT control_gate_readback_observations_mode
        CHECK (reconciliation_mode IN ('observe', 'enforce'))
);

CREATE TRIGGER control_gate_readback_observations_immutable
    BEFORE UPDATE OR DELETE ON scheduler.control_gate_readback_observations
    FOR EACH ROW EXECUTE FUNCTION scheduler.control_plan_rows_are_immutable();
