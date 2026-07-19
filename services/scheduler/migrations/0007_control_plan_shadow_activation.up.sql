-- 0007_control_plan_shadow_activation (PR 4.3c-1)
-- Shadow ACTIVATION: relax the 0003 lifecycle CHECKs to admit the shadow_active
-- state + its two edges, add the append-only command-intent outbox, and add the
-- mutable one-per-scope authority mutex. Relaxes CHECKs via THIS new migration,
-- never by editing the applied 0003 pair.

-- 1) Admit the shadow_active state + the two new edges
--    (shadow_activated: approved_for_shadow -> shadow_active; and the emergency
--    invalidated: shadow_active -> invalidated). Supersede-of-active is 4.3c-2.
ALTER TABLE scheduler.control_state_transitions
    DROP CONSTRAINT control_state_transitions_type,
    DROP CONSTRAINT control_state_transitions_from_state,
    DROP CONSTRAINT control_state_transitions_to_state,
    DROP CONSTRAINT control_state_transitions_edge_graph;

ALTER TABLE scheduler.control_state_transitions
    ADD CONSTRAINT control_state_transitions_type
        CHECK (
            transition_type IN (
                'draft_created', 'review_requested', 'shadow_approved',
                'shadow_activated', 'cancelled', 'superseded', 'invalidated'
            )
        ),
    ADD CONSTRAINT control_state_transitions_from_state
        CHECK (
            (transition_sequence = 1 AND from_state IS NULL)
            OR (transition_sequence > 1
                AND from_state IS NOT NULL
                AND from_state IN (
                    'draft', 'under_review', 'approved_for_shadow', 'shadow_active'
                ))
        ),
    ADD CONSTRAINT control_state_transitions_to_state
        CHECK (
            to_state IN (
                'draft', 'under_review', 'approved_for_shadow', 'shadow_active',
                'cancelled', 'superseded', 'invalidated'
            )
        ),
    -- COALESCE is REQUIRED: a tuple CHECK containing SQL NULL evaluates to UNKNOWN,
    -- and a CHECK passes on UNKNOWN, so a NULL from_state would slip an illegal edge.
    ADD CONSTRAINT control_state_transitions_edge_graph
        CHECK (
            (transition_type, COALESCE(from_state, '__initial__'), to_state) IN (
                ('draft_created', '__initial__', 'draft'),
                ('review_requested', 'draft', 'under_review'),
                ('shadow_approved', 'under_review', 'approved_for_shadow'),
                ('cancelled', 'draft', 'cancelled'),
                ('cancelled', 'under_review', 'cancelled'),
                ('cancelled', 'approved_for_shadow', 'cancelled'),
                ('superseded', 'approved_for_shadow', 'superseded'),
                ('invalidated', 'draft', 'invalidated'),
                ('invalidated', 'under_review', 'invalidated'),
                ('invalidated', 'approved_for_shadow', 'invalidated'),
                ('shadow_activated', 'approved_for_shadow', 'shadow_active'),
                ('invalidated', 'shadow_active', 'invalidated')
            )
        );

-- 2) Append-only command-intent outbox (one row per compiled CommandIntent).
--    Reuses the 0001 immutability trigger fn. mode is always 'shadow'.
CREATE TABLE scheduler.control_command_outbox (
    intent_id UUID NOT NULL,
    correlation_id UUID NOT NULL,
    request_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    canonical_gate_id TEXT NOT NULL,
    event_kind TEXT NOT NULL,
    event_sequence INTEGER NOT NULL,
    gate_event_sequence INTEGER NOT NULL,
    device_id TEXT NOT NULL,
    adapter_gate_id TEXT NOT NULL,
    capability_release_id TEXT NOT NULL,
    capability_hash CHAR(64) NOT NULL,
    target_position_m DOUBLE PRECISION NOT NULL,
    target_level INTEGER NOT NULL,
    not_before TIMESTAMPTZ NOT NULL,
    deadline TIMESTAMPTZ NOT NULL,
    mode TEXT NOT NULL,
    intent_document_text TEXT NOT NULL,
    intent_content_hash CHAR(64) NOT NULL,
    plan_id UUID NOT NULL,
    plan_version INTEGER NOT NULL,
    activation_transition_sequence INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT control_command_outbox_pkey PRIMARY KEY (intent_id),
    CONSTRAINT control_command_outbox_idempotency_key UNIQUE (idempotency_key),
    -- B2: uniqueness on the GLOBAL event_sequence (gate_event_sequence restarts
    -- per gate and would collide across gates).
    CONSTRAINT control_command_outbox_event_key
        UNIQUE (plan_id, plan_version, event_sequence),
    CONSTRAINT control_command_outbox_run_fkey
        FOREIGN KEY (plan_id, plan_version)
        REFERENCES scheduler.control_plan_runs (plan_id, plan_version)
        ON DELETE RESTRICT,
    CONSTRAINT control_command_outbox_mode CHECK (mode = 'shadow'),
    CONSTRAINT control_command_outbox_kind
        CHECK (event_kind IN ('open', 'trim', 'close')),
    CONSTRAINT control_command_outbox_level
        CHECK (target_level BETWEEN 0 AND 65535),
    CONSTRAINT control_command_outbox_open_trim_positive
        CHECK (event_kind = 'close' OR target_position_m > 0),
    CONSTRAINT control_command_outbox_close_zero
        CHECK (event_kind <> 'close' OR target_position_m = 0)
);

CREATE TRIGGER control_command_outbox_immutable
    BEFORE UPDATE OR DELETE ON scheduler.control_command_outbox
    FOR EACH ROW EXECUTE FUNCTION scheduler.control_plan_rows_are_immutable();

-- 3) One-per-scope authority mutex — a MUTABLE materialized current-authority
--    index (NOT the audit authority; that stays the append-only transitions).
--    The (section_id, gate_id) PK is the DB-level one-per-scope lock: a second
--    activation on an occupied scope raises a unique violation. Rows are INSERTed
--    on activation and DELETEd when the holder leaves shadow_active, so it has NO
--    immutability trigger. 5.2 owns restart-safe re-derivation.
CREATE TABLE scheduler.control_active_gate_authority (
    section_id TEXT NOT NULL,
    gate_id TEXT NOT NULL,
    plan_id UUID NOT NULL,
    plan_version INTEGER NOT NULL,
    activation_transition_sequence INTEGER NOT NULL,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT control_active_gate_authority_pkey PRIMARY KEY (section_id, gate_id),
    CONSTRAINT control_active_gate_authority_run_fkey
        FOREIGN KEY (plan_id, plan_version)
        REFERENCES scheduler.control_plan_runs (plan_id, plan_version)
        ON DELETE RESTRICT
);
