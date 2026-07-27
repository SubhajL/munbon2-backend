# V5 Hybrid Section Master Activation

This procedure activates the immutable section-area overlay without editing
`gis.zone`. Excel Sheet1 is authoritative for sections 03–34; GIS remains
authoritative for RMC and 4L-RMC sections 35–43. The approved result is 41
sections and 45,204 rai.

## Preconditions

1. Deploy the exact merged revision containing the tracked V5 workbook and
   `services/ros-gis-integration/data/requirement_sources.json`.
2. Keep control execution disabled and machine-command authority false.
3. Keep `DAILY_REQUIREMENT_STARTUP_CATCHUP_ENABLED=false` and
   `DAILY_REQUIREMENT_SCHEDULE_ENABLED=false`.
4. Confirm ros-gis-integration and bff-water-planning use the same local
   `POSTGRES_URL` database. `REQUIREMENT_SOURCE_POSTGRES_URL` is separate and
   identifies the database containing `gis.zone`.
5. Apply ros-gis-integration migration `0001_dataset_version_parent` and verify
   its checksum with `python migrations/migrate.py status`.

Do not print connection strings. Compare only parsed host, port, and database
names through the deployment secret manager.

## Manual activation

Set `DAILY_REQUIREMENT_ENABLED=true` only after all producer inputs pass their
preflight, then restart ros-gis-integration. This enables the authenticated
manual producer route without enabling startup catch-up or the recurring
schedule.

Invoke one manual run through:

```text
POST /api/v1/water-requirements/runs
```

The source loader writes a new immutable `section_master` dataset and atomically
marks it active. It does not update `gis.zone`. A missing or incomplete source
returns `failed_incomplete_source`; do not bypass that result.

## Database verification

Run these read-only checks against the shared local database:

```sql
SELECT dataset_version_id, source_hash, source_description
FROM ros_gis.dataset_versions
WHERE dataset_kind = 'section_master' AND status = 'active';

SELECT count(*) AS section_count, sum(area_rai) AS total_area_rai
FROM ros_gis.sections_current;

SELECT right(section_id, 2) AS section_number, area_rai
FROM ros_gis.sections_current
WHERE right(section_id, 2) IN ('21', '22', '35', '43')
ORDER BY section_id;
```

Acceptance requires one active dataset, 41 rows, a 45,204-rai total, and spot
areas 503, 1,907, 358, and 618 rai for sections 21, 22, 35, and 43 respectively.
Then verify the BFF reads the same roster before accepting planning-depth
writes.

After verification, return `DAILY_REQUIREMENT_ENABLED` to its approved
operational value. Leave both catch-up and schedule flags false unless their
separate operational approval has been granted.

## Scope boundary

This activates section areas and geometry lineage only. Flow-monitoring remains
pinned to V3 hydraulic artifacts. V5 sill, FSL, and `q_max` values require a
separate generator change, regenerated locked artifacts, and independent
runtime acceptance.
