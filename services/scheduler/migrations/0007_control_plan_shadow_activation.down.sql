-- 0007_control_plan_shadow_activation DOWN (PR 4.3c-1)
-- Reverse the activation surface and restore the 0003 lifecycle CHECKs. Re-adding
-- the narrower 0003 to_state/from_state CHECKs VALIDATES existing rows, so this
-- fails closed if any shadow_active transition exists (forward-fix, never down
-- once activations exist) — matching the 0003 down convention.

DROP TABLE scheduler.control_active_gate_authority;
DROP TABLE scheduler.control_command_outbox;

ALTER TABLE scheduler.control_state_transitions
    DROP CONSTRAINT control_state_transitions_type,
    DROP CONSTRAINT control_state_transitions_from_state,
    DROP CONSTRAINT control_state_transitions_to_state,
    DROP CONSTRAINT control_state_transitions_edge_graph;

ALTER TABLE scheduler.control_state_transitions
    ADD CONSTRAINT control_state_transitions_type
        CHECK (
            transition_type IN (
                'draft_created', 'review_requested', 'shadow_approved',
                'cancelled', 'superseded', 'invalidated'
            )
        ),
    ADD CONSTRAINT control_state_transitions_from_state
        CHECK (
            (transition_sequence = 1 AND from_state IS NULL)
            OR (transition_sequence > 1
                AND from_state IS NOT NULL
                AND from_state IN (
                    'draft', 'under_review', 'approved_for_shadow'
                ))
        ),
    ADD CONSTRAINT control_state_transitions_to_state
        CHECK (
            to_state IN (
                'draft', 'under_review', 'approved_for_shadow',
                'cancelled', 'superseded', 'invalidated'
            )
        ),
    ADD CONSTRAINT control_state_transitions_edge_graph
        CHECK (
            (transition_type, COALESCE(from_state, '__initial__'), to_state) IN (
                ('draft_created', '__initial__', 'draft'),
                ('review_requested', 'draft', 'under_review'),
                ('shadow_approved', 'under_review', 'approved_for_shadow'),
                ('cancelled', 'draft', 'cancelled'),
                ('cancelled', 'under_review', 'cancelled'),
                ('cancelled', 'approved_for_shadow', 'cancelled'),
                ('superseded', 'approved_for_shadow', 'superseded'),
                ('invalidated', 'draft', 'invalidated'),
                ('invalidated', 'under_review', 'invalidated'),
                ('invalidated', 'approved_for_shadow', 'invalidated')
            )
        );
