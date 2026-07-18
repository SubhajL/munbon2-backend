-- 0004_control_plan_list_indexes (PR 4.4a-3)
-- Additive: INDEXES ONLY. No table/column/trigger/row change, so the ORM<->DDL
-- drift lock (which mirrors CREATE TABLE column sets) and the immutability
-- triggers are untouched. These back the bounded list projection: the keyset
-- order plus the exact-match lineage filters the list route exposes.

-- Keyset pagination order (created_at DESC, plan_id DESC, plan_version DESC).
-- plan_version is the final tie-break so the key is the row's TOTAL identity
-- (plan_id, plan_version) and pagination is provably total (no skip/duplicate).
CREATE INDEX control_plan_runs_created_at_plan_id_idx
    ON scheduler.control_plan_runs (created_at DESC, plan_id DESC, plan_version DESC);

-- Exact-match lineage filters served by the list route.
CREATE INDEX control_plan_runs_model_snapshot_id_idx
    ON scheduler.control_plan_runs (model_snapshot_id);

CREATE INDEX control_plan_runs_prediction_run_id_idx
    ON scheduler.control_plan_runs (prediction_run_id);

CREATE INDEX control_plan_runs_requirement_run_id_idx
    ON scheduler.control_plan_runs (requirement_run_id);

-- Horizon-window range filters (horizon_start_gte / horizon_end_lte).
CREATE INDEX control_plan_runs_horizon_idx
    ON scheduler.control_plan_runs (horizon_start, horizon_end);
