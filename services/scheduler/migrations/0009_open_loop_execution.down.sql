-- 0009_open_loop_execution DOWN (PR 5.2b)
-- Purely additive migration → clean drop (no constraint was altered). The trigger
-- drops with the table. Once execution rows exist, forward-fix rather than down.

DROP TABLE scheduler.control_command_execution_events;
