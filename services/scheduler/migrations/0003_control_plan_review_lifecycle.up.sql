-- 0003_control_plan_review_lifecycle (PR 4.3b)
-- Relax the four narrow 0001 transition CHECKs to admit the review lifecycle.
-- Adds NO table/column/trigger (done-gate: no intent table). The 0001
-- immutability trigger already keeps control_state_transitions append-only.

ALTER TABLE scheduler.control_state_transitions
    DROP CONSTRAINT control_state_transitions_initial_only,
    DROP CONSTRAINT control_state_transitions_type,
    DROP CONSTRAINT control_state_transitions_from_initial,
    DROP CONSTRAINT control_state_transitions_to_draft;

ALTER TABLE scheduler.control_state_transitions
    ADD CONSTRAINT control_state_transitions_sequence
        CHECK (
            (transition_sequence = 1 AND transition_type = 'draft_created')
            OR (transition_sequence > 1 AND transition_type <> 'draft_created')
        ),
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
    -- The lifecycle edge graph. COALESCE is REQUIRED: a tuple comparison that
    -- contains a SQL NULL evaluates to UNKNOWN, and a CHECK passes on UNKNOWN
    -- (it only fails on FALSE), so a NULL from_state would slip an illegal edge.
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
