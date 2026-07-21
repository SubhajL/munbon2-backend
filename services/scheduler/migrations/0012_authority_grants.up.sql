-- 0012_authority_grants (PR 7.1a)
-- Execution-authority grant backend: an IMMUTABLE per-plan-version grant row binding the
-- approved release identity (the 6.1b anchor triple), the commandability evidence, the exact
-- capability release/hash, the plan's physical gate/path scope, and the approved operating
-- envelope — plus an APPEND-ONLY lifecycle ledger (granted -> renewed* -> revoked) whose fold
-- is the ONLY source of current authority status. NOTHING here executes: no route/flag
-- combination can actuate after this migration, no grant is seeded, and `operator_approved`
-- execution mode remains refused in code. `control_active_gate_authority` (0007) is the
-- SHADOW scope mutex; these tables are EXECUTION authority — always qualify the former.
-- Purely additive; reuses the 0001 immutability trigger. Canonical documents are TEXT
-- (never JSONB).

CREATE TABLE scheduler.control_authority_grants (
    grant_id UUID NOT NULL,
    authority_schema_version SMALLINT NOT NULL,
    plan_id UUID NOT NULL,
    plan_version INTEGER NOT NULL,
    model_release_id TEXT NOT NULL,
    model_release_content_hash CHAR(64) NOT NULL,
    engine_descriptor_content_hash CHAR(64) NOT NULL,
    model_release_commandable BOOLEAN NOT NULL,
    commandability_evidence_document_text TEXT NOT NULL,
    commandability_evidence_sha256 CHAR(64) NOT NULL,
    capability_release_id TEXT NOT NULL,
    capability_hash CHAR(64) NOT NULL,
    scope_document_text TEXT NOT NULL,
    scope_sha256 CHAR(64) NOT NULL,
    intent_set_sha256 CHAR(64) NOT NULL,
    flow_lower_exclusive_m3s DOUBLE PRECISION NOT NULL,
    flow_upper_inclusive_m3s DOUBLE PRECISION NOT NULL,
    initialization_document_text TEXT NOT NULL,
    initialization_sha256 CHAR(64) NOT NULL,
    maximum_continuous_open_seconds INTEGER NOT NULL,
    maximum_intermediate_trims SMALLINT NOT NULL,
    grant_document_text TEXT NOT NULL,
    grant_content_sha256 CHAR(64) NOT NULL,
    created_by_subject TEXT NOT NULL,
    request_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT control_authority_grants_pkey PRIMARY KEY (grant_id),
    -- intent_set_sha256: the order-independent hash over the plan's outbox
    -- intent content hashes (the activation-freeze pattern) — binds the grant
    -- to the EXACT immutable intent batch, so an altered/extra/missing intent
    -- fails the execution predicate structurally.
    -- The grant authorizes ONE immutable plan version; re-authorization after
    -- revocation requires a NEW plan version (revocation is deliberately final
    -- for a version — no un-revoke, no second grant).
    CONSTRAINT control_authority_grants_run_fkey
        FOREIGN KEY (plan_id, plan_version)
        REFERENCES scheduler.control_plan_runs (plan_id, plan_version)
        ON DELETE RESTRICT,
    CONSTRAINT control_authority_grants_one_per_plan UNIQUE (plan_id, plan_version),
    -- Replay idempotency: a byte-identical grant request maps to the same row.
    CONSTRAINT control_authority_grants_content UNIQUE (grant_content_sha256),
    CONSTRAINT control_authority_grants_schema_version
        CHECK (authority_schema_version = 1),
    CONSTRAINT control_authority_grants_plan_version CHECK (plan_version > 0),
    -- DB-level backstop for the code-level rejection of non-commandable evidence:
    -- a grant row asserting a non-commandable release can never exist.
    CONSTRAINT control_authority_grants_commandable
        CHECK (model_release_commandable IS TRUE),
    CONSTRAINT control_authority_grants_flow_envelope
        CHECK (flow_lower_exclusive_m3s >= 0
               AND flow_upper_inclusive_m3s > flow_lower_exclusive_m3s),
    CONSTRAINT control_authority_grants_open_seconds
        CHECK (maximum_continuous_open_seconds > 0),
    CONSTRAINT control_authority_grants_trims
        CHECK (maximum_intermediate_trims BETWEEN 0 AND 2)
);

CREATE TRIGGER control_authority_grants_immutable
    BEFORE UPDATE OR DELETE ON scheduler.control_authority_grants
    FOR EACH ROW EXECUTE FUNCTION scheduler.control_plan_rows_are_immutable();

CREATE TABLE scheduler.control_authority_grant_events (
    event_id UUID NOT NULL,
    grant_id UUID NOT NULL,
    event_sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    effective_expires_at TIMESTAMPTZ,
    shadow_evidence_sha256 CHAR(64),
    hold_drill_evidence_sha256 CHAR(64),
    rollback_drill_evidence_sha256 CHAR(64),
    evidence_manifest_document_text TEXT,
    evidence_manifest_sha256 CHAR(64),
    actor_subject TEXT NOT NULL,
    reason TEXT NOT NULL,
    authorization_evidence_document_text TEXT NOT NULL,
    authorization_evidence_sha256 CHAR(64) NOT NULL,
    event_document_text TEXT NOT NULL,
    event_content_sha256 CHAR(64) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT control_authority_grant_events_pkey PRIMARY KEY (event_id),
    CONSTRAINT control_authority_grant_events_grant_fkey
        FOREIGN KEY (grant_id)
        REFERENCES scheduler.control_authority_grants (grant_id)
        ON DELETE RESTRICT,
    CONSTRAINT control_authority_grant_events_sequence UNIQUE (grant_id, event_sequence),
    CONSTRAINT control_authority_grant_events_sequence_positive
        CHECK (event_sequence > 0),
    CONSTRAINT control_authority_grant_events_type
        CHECK (event_type IN ('granted', 'renewed', 'revoked')),
    -- The birth event is exactly sequence 1 and ONLY sequence 1.
    CONSTRAINT control_authority_grant_events_granted_first
        CHECK ((event_type = 'granted') = (event_sequence = 1)),
    -- granted/renewed carry a future expiry + a COMPLETE refreshed evidence set
    -- (a renewal must re-prove, never just extend a timestamp); revoked carries
    -- neither (revocation needs an actor + reason, not fresh drill evidence).
    CONSTRAINT control_authority_grant_events_shape
        CHECK (
            (event_type IN ('granted', 'renewed')
             AND effective_expires_at IS NOT NULL
             AND effective_expires_at > occurred_at
             AND shadow_evidence_sha256 IS NOT NULL
             AND hold_drill_evidence_sha256 IS NOT NULL
             AND rollback_drill_evidence_sha256 IS NOT NULL
             AND evidence_manifest_document_text IS NOT NULL
             AND evidence_manifest_sha256 IS NOT NULL)
            OR (event_type = 'revoked'
                AND effective_expires_at IS NULL
                AND shadow_evidence_sha256 IS NULL
                AND hold_drill_evidence_sha256 IS NULL
                AND rollback_drill_evidence_sha256 IS NULL
                AND evidence_manifest_document_text IS NULL
                AND evidence_manifest_sha256 IS NULL)
        )
);

-- Revocation is terminal and unique: two concurrent revokes race to ONE row.
CREATE UNIQUE INDEX control_authority_grant_events_one_revocation
    ON scheduler.control_authority_grant_events (grant_id)
    WHERE event_type = 'revoked';

CREATE TRIGGER control_authority_grant_events_immutable
    BEFORE UPDATE OR DELETE ON scheduler.control_authority_grant_events
    FOR EACH ROW EXECUTE FUNCTION scheduler.control_plan_rows_are_immutable();
