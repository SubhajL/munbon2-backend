-- 0008_control_plan_active_supersede DOWN (PR 4.3c-2)
-- Restore the 0007 edge graph (without the active-supersede edge). Re-adding the
-- narrower CHECK VALIDATES existing rows, so this fails closed if any
-- (superseded, shadow_active, superseded) transition exists (forward-fix, never
-- down once graceful supersedes exist).

ALTER TABLE scheduler.control_state_transitions
    DROP CONSTRAINT control_state_transitions_edge_graph;

ALTER TABLE scheduler.control_state_transitions
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
                ('invalidated', 'approved_for_shadow', 'invalidated'),
                ('shadow_activated', 'approved_for_shadow', 'shadow_active'),
                ('invalidated', 'shadow_active', 'invalidated')
            )
        );
