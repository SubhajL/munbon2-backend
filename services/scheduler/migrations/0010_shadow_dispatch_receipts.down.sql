-- 0010_shadow_dispatch_receipts DOWN (PR 6.3a)
-- Purely additive migration → a clean drop. The immutability trigger is dropped with the
-- table. No 0007/0009 object is touched, so this rolls back independently.
DROP TABLE scheduler.control_command_validation_receipts;
