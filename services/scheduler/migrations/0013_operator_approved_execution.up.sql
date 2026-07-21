-- PR 7.2: immutable Scheduler copy of SCADA machine-execution outcomes.
CREATE TABLE scheduler.control_command_execution_receipts (
    intent_id UUID NOT NULL,
    plan_id UUID NOT NULL,
    plan_version INTEGER NOT NULL,
    grant_id UUID NOT NULL,
    authority_not_after TIMESTAMPTZ NOT NULL,
    receipt_id UUID NOT NULL,
    idempotency_key TEXT NOT NULL,
    original_intent_content_hash CHAR(64) NOT NULL,
    execution_intent_content_hash CHAR(64) NOT NULL,
    capability_hash CHAR(64) NOT NULL,
    purpose TEXT NOT NULL,
    status TEXT NOT NULL,
    reason_code TEXT,
    target_level INTEGER NOT NULL,
    observed_level INTEGER,
    readback_quality TEXT NOT NULL,
    writes_document_text TEXT NOT NULL,
    executed_at TIMESTAMPTZ NOT NULL,
    receipt_document_text TEXT NOT NULL,
    receipt_content_sha256 CHAR(64) NOT NULL,
    dispatch_worker_id TEXT NOT NULL,
    dispatched_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT control_command_execution_receipts_pkey PRIMARY KEY (intent_id),
    CONSTRAINT control_command_execution_receipts_run_fkey
        FOREIGN KEY (plan_id, plan_version)
        REFERENCES scheduler.control_plan_runs (plan_id, plan_version) ON DELETE RESTRICT,
    CONSTRAINT control_command_execution_receipts_grant_fkey
        FOREIGN KEY (grant_id)
        REFERENCES scheduler.control_authority_grants (grant_id) ON DELETE RESTRICT,
    CONSTRAINT control_command_execution_receipts_idem UNIQUE (idempotency_key),
    CONSTRAINT control_command_execution_receipts_purpose
        CHECK (purpose IN ('operator_approved', 'fail_safe_close')),
    CONSTRAINT control_command_execution_receipts_status
        CHECK (status IN ('execution_succeeded', 'execution_rejected',
                          'execution_failed', 'readback_mismatch', 'execution_in_doubt')),
    CONSTRAINT control_command_execution_receipts_reason
        CHECK ((status = 'execution_succeeded' AND reason_code IS NULL)
               OR (status <> 'execution_succeeded' AND reason_code IS NOT NULL)),
    CONSTRAINT control_command_execution_receipts_target CHECK (target_level BETWEEN 0 AND 65535),
    CONSTRAINT control_command_execution_receipts_observed
        CHECK (observed_level IS NULL OR observed_level BETWEEN 0 AND 65535),
    CONSTRAINT control_command_execution_receipts_success_readback
        CHECK (status <> 'execution_succeeded'
               OR (readback_quality = 'ok' AND observed_level = target_level))
);

CREATE TRIGGER control_command_execution_receipts_immutable
    BEFORE UPDATE OR DELETE ON scheduler.control_command_execution_receipts
    FOR EACH ROW EXECUTE FUNCTION scheduler.control_plan_rows_are_immutable();
