-- Rollback 0002: drop only the new trigger and table. The shared
-- scheduler.control_plan_rows_are_immutable() function and the 0001 tables are
-- owned by 0001 and left intact.

DROP TRIGGER section_delivery_ledger_immutable
    ON scheduler.section_delivery_ledger;

DROP TABLE scheduler.section_delivery_ledger;
