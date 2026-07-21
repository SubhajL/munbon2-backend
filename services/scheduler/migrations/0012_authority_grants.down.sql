-- Rollback 0012_authority_grants.
-- REFUSES while ANY authority grant exists: a grant row is externally-approved
-- authority evidence that cannot be reconstructed after a DROP, so once evidence
-- exists this migration is forward-fix-only. On empty tables it drops cleanly
-- (triggers and the partial revocation index drop with their tables).
-- Lock the parent BEFORE the emptiness check. This blocks concurrent issuance
-- while allowing a populated table to refuse immediately without waiting on a
-- child-table writer. Only an empty rollback proceeds to lock and drop the child.

LOCK TABLE scheduler.control_authority_grants IN ACCESS EXCLUSIVE MODE;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM scheduler.control_authority_grants) THEN
        RAISE EXCEPTION
            'cannot roll back 0012: authority grant evidence exists — '
            'forward-fix with a new migration instead';
    END IF;
END
$$;

LOCK TABLE scheduler.control_authority_grant_events IN ACCESS EXCLUSIVE MODE;

DROP TABLE scheduler.control_authority_grant_events;
DROP TABLE scheduler.control_authority_grants;
