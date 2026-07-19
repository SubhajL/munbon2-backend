-- 0008_control_plan_active_supersede (PR 4.3c-2)
-- Graceful supersede of an ACTIVE plan: admit the (superseded, shadow_active,
-- superseded) edge. from_state already includes shadow_active and to_state already
-- includes superseded (0007/0003), so ONLY the edge graph widens. Relaxes the 0007
-- CHECK via THIS new migration, never by editing the applied 0007 pair.

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
                ('invalidated', 'shadow_active', 'invalidated'),
                ('superseded', 'shadow_active', 'superseded')
            )
        );
