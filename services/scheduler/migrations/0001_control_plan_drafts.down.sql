-- Rollback 0001_control_plan_drafts: drop triggers and tables child-first,
-- then the shared trigger function. The scheduler schema and the migration
-- registry are owned by the runner and are left intact.

DROP TRIGGER control_state_transitions_immutable
    ON scheduler.control_state_transitions;
DROP TRIGGER gate_plan_events_immutable ON scheduler.gate_plan_events;
DROP TRIGGER control_plan_requirements_immutable
    ON scheduler.control_plan_requirements;
DROP TRIGGER control_plan_runs_immutable ON scheduler.control_plan_runs;

DROP TABLE scheduler.control_state_transitions;
DROP TABLE scheduler.gate_plan_events;
DROP TABLE scheduler.control_plan_requirements;
DROP TABLE scheduler.control_plan_runs;

DROP FUNCTION scheduler.control_plan_rows_are_immutable();
