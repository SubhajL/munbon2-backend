LOCK TABLE scheduler.control_command_execution_receipts IN ACCESS EXCLUSIVE MODE;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM scheduler.control_command_execution_receipts) THEN
        RAISE EXCEPTION '0013 contains machine execution evidence; forward-fix only';
    END IF;
END $$;

DROP TABLE scheduler.control_command_execution_receipts;
