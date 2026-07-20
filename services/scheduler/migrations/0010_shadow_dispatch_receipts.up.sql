-- 0010_shadow_dispatch_receipts (PR 6.3a)
-- Append-only durable store of the SCADA 6.0 ValidationReceipt the shadow dispatcher
-- gets back from POST /internal/v1/command-intents/validate. EXACTLY ONE receipt per
-- command-intent (intent_id PK) — the DB backstop that makes an at-least-once dispatch
-- an exactly-once persisted effect: a retried dispatch replays SCADA's idempotent (and
-- byte-identical) receipt, and the second INSERT ... ON CONFLICT (intent_id) DO NOTHING
-- is a no-op. idempotency_key UNIQUE is the second backstop (mirrors the 0007 outbox +
-- the SCADA receipt store). Purely additive: no existing constraint is altered.
-- Reuses the 0001 immutability trigger function. Canonical documents are TEXT (never JSONB).

CREATE TABLE scheduler.control_command_validation_receipts (
    intent_id UUID NOT NULL,
    plan_id UUID NOT NULL,
    plan_version INTEGER NOT NULL,
    receipt_id UUID NOT NULL,
    correlation_id UUID NOT NULL,
    request_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    intent_content_hash CHAR(64) NOT NULL,
    capability_hash CHAR(64) NOT NULL,
    status TEXT NOT NULL,
    reason_code TEXT,
    validated_at TIMESTAMPTZ NOT NULL,
    receipt_document_text TEXT NOT NULL,
    receipt_content_sha256 CHAR(64) NOT NULL,
    dispatch_worker_id TEXT,
    dispatched_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT control_command_validation_receipts_pkey PRIMARY KEY (intent_id),
    -- No FK to control_command_outbox on intent_id: keep 0010 additively independent of
    -- the 0007 outbox migration (identical rationale to 0009). The run FK is enough.
    CONSTRAINT control_command_validation_receipts_run_fkey
        FOREIGN KEY (plan_id, plan_version)
        REFERENCES scheduler.control_plan_runs (plan_id, plan_version)
        ON DELETE RESTRICT,
    CONSTRAINT control_command_validation_receipts_idem UNIQUE (idempotency_key),
    CONSTRAINT control_command_validation_receipts_status
        CHECK (status IN ('validation_accepted', 'validation_rejected')),
    -- Mirror the ValidationReceipt model invariant: accepted => null reason; rejected => a reason.
    CONSTRAINT control_command_validation_receipts_reason
        CHECK (
            (status = 'validation_accepted' AND reason_code IS NULL)
            OR (status = 'validation_rejected' AND reason_code IS NOT NULL)
        ),
    -- The frozen 6.0 rejection vocabulary (matches the validation-receipt contract).
    CONSTRAINT control_command_validation_receipts_reason_vocab
        CHECK (
            reason_code IS NULL
            OR reason_code IN (
                'schema_invalid', 'capability_mismatch', 'target_invalid',
                'not_before_violation', 'deadline_expired', 'lineage_mismatch',
                'freshness_failed', 'idempotency_conflict'
            )
        )
);

CREATE TRIGGER control_command_validation_receipts_immutable
    BEFORE UPDATE OR DELETE ON scheduler.control_command_validation_receipts
    FOR EACH ROW EXECUTE FUNCTION scheduler.control_plan_rows_are_immutable();
