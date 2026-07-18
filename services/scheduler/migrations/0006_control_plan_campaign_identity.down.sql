-- Rollback 0006_control_plan_campaign_identity.
-- REFUSES once any REAL (non-legacy) campaign exists. Two independent guards:
--   1. a mapping row whose campaign_id <> plan_id (a fresh-campaign or a rolled
--      version — never a backfill singleton), OR
--   2. any campaign carrying more than one version.
-- Either means the campaign->version identity is load-bearing and cannot be
-- reconstructed after a DROP, so down is forward-fix-only. On a table holding
-- ONLY legacy singletons (campaign_id = plan_id, one version each) it drops the
-- mapping table cleanly (its trigger and index drop with it).

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM scheduler.control_plan_campaign_versions
        WHERE campaign_id <> plan_id
    ) THEN
        RAISE EXCEPTION
            'cannot roll back 0006: a non-singleton campaign mapping exists '
            '(campaign_id <> plan_id) — the campaign identity is load-bearing; '
            'forward-fix with a new migration instead';
    END IF;
    IF EXISTS (
        SELECT 1 FROM scheduler.control_plan_campaign_versions
        GROUP BY campaign_id HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION
            'cannot roll back 0006: a campaign carries more than one version — '
            'forward-fix with a new migration instead';
    END IF;
END
$$;

DROP TABLE scheduler.control_plan_campaign_versions;
