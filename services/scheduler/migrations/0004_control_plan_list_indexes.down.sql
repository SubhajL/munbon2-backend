-- 0004_control_plan_list_indexes (down) — drop the additive list indexes only.
-- No table/column/row is touched, so this rolls back cleanly at any time.
DROP INDEX scheduler.control_plan_runs_created_at_plan_id_idx;
DROP INDEX scheduler.control_plan_runs_model_snapshot_id_idx;
DROP INDEX scheduler.control_plan_runs_prediction_run_id_idx;
DROP INDEX scheduler.control_plan_runs_requirement_run_id_idx;
DROP INDEX scheduler.control_plan_runs_horizon_idx;
