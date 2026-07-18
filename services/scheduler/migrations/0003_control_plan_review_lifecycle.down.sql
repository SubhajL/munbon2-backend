-- Rollback 0003: restore the four original narrow 0001 CHECK definitions
-- exactly. This only succeeds while no transition with sequence > 1 exists;
-- once lifecycle rows have been written, the immutable rows cannot satisfy the
-- narrow checks — forward-fix instead of rolling down.

ALTER TABLE scheduler.control_state_transitions
    DROP CONSTRAINT control_state_transitions_sequence,
    DROP CONSTRAINT control_state_transitions_type,
    DROP CONSTRAINT control_state_transitions_from_state,
    DROP CONSTRAINT control_state_transitions_to_state,
    DROP CONSTRAINT control_state_transitions_edge_graph;

ALTER TABLE scheduler.control_state_transitions
    ADD CONSTRAINT control_state_transitions_initial_only
        CHECK (transition_sequence = 1),
    ADD CONSTRAINT control_state_transitions_type
        CHECK (transition_type = 'draft_created'),
    ADD CONSTRAINT control_state_transitions_from_initial
        CHECK (from_state IS NULL),
    ADD CONSTRAINT control_state_transitions_to_draft
        CHECK (to_state = 'draft');
