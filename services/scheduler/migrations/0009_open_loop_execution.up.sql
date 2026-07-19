-- 0009_open_loop_execution (PR 5.2b)
-- Append-only per-intent open-loop EXECUTION audit log. One row per execution-state
-- change of a command-intent (claimed / missed / invalidated) plus plan-level
-- operator events (held / resumed). The plan lifecycle stays event-sourced in
-- control_state_transitions; THIS table records what the worker did to each intent.
-- Purely additive: no existing constraint is altered (the invalidated:
-- shadow_active->invalidated edge a missed deadline drives already exists in 0007).
-- Reuses the 0001 immutability trigger function. Canonical documents are TEXT.

CREATE TABLE scheduler.control_command_execution_events (
    event_id UUID NOT NULL,
    plan_id UUID NOT NULL,
    plan_version INTEGER NOT NULL,
    intent_id UUID,
    event_type TEXT NOT NULL,
    worker_id TEXT,
    detail_document_text TEXT,
    occurred_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT control_command_execution_events_pkey PRIMARY KEY (event_id),
    CONSTRAINT control_command_execution_events_run_fkey
        FOREIGN KEY (plan_id, plan_version)
        REFERENCES scheduler.control_plan_runs (plan_id, plan_version)
        ON DELETE RESTRICT,
    -- No FK to control_command_outbox on intent_id: the worker only ever writes
    -- events for intents it loaded from the outbox, and the UNIQUE(intent_id,
    -- event_type) below is the double-claim backstop — so a hard FK adds no real
    -- integrity here while it WOULD couple this log to the 0007 outbox migration
    -- (blocking an independent rollback of 0007). Keep 0009 additively independent.
    CONSTRAINT control_command_execution_events_type
        CHECK (event_type IN ('claimed', 'missed', 'invalidated', 'held', 'resumed')),
    -- Per-intent events must carry an intent; plan-level events must not.
    CONSTRAINT control_command_execution_events_intent_scope
        CHECK (
            (event_type IN ('claimed', 'missed', 'invalidated')
             AND intent_id IS NOT NULL)
            OR (event_type IN ('held', 'resumed') AND intent_id IS NULL)
        )
);

-- At most ONE TERMINAL event (claimed | missed | invalidated) per intent — the DB
-- backstop that makes the per-intent execution state a well-defined fold even under
-- concurrent workers: a claim and an invalidate for the SAME intent can never both
-- land (the second 23505s). A per-kind UNIQUE(intent_id, event_type) would WRONGLY
-- admit both (different event_type), producing a contradictory claimed+invalidated
-- pair. Plan-level held/resumed (intent_id NULL) are excluded by the predicate, so a
-- plan may be held/resumed repeatedly.
CREATE UNIQUE INDEX control_command_execution_events_one_terminal_per_intent
    ON scheduler.control_command_execution_events (intent_id)
    WHERE event_type IN ('claimed', 'missed', 'invalidated');

CREATE TRIGGER control_command_execution_events_immutable
    BEFORE UPDATE OR DELETE ON scheduler.control_command_execution_events
    FOR EACH ROW EXECUTE FUNCTION scheduler.control_plan_rows_are_immutable();
