-- 0011_gate_readback_observations DOWN (PR 6.3b)
-- Purely additive → clean drop; the immutability trigger drops with the table. No prior
-- migration object is touched, so this rolls back independently.
DROP TABLE scheduler.control_gate_readback_observations;
