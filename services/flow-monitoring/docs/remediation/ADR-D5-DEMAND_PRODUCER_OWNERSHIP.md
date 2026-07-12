# ADR D5 — Demand-producer ownership (Wave 2.6a)

**Status:** Proposed 2026-07-12 (adopted provisionally for Wave-2 sequencing; awaiting
maintainer ratification like D1–D4 in [PROGRAM_REVIEW_2026-07-09.md](PROGRAM_REVIEW_2026-07-09.md) §2.0).
**Driver:** gpt-5.6-sol adversarial re-review finding #9
(`.codex/coding-logs/wave2-4-rereview-gpt56sol-2026-07-12.md`; folded into
[WAVE_2-4_PLAN_2026-07-12.md](WAVE_2-4_PLAN_2026-07-12.md) §1.5).

## Context

Three services touch weekly demand production and none of them can actually do it:

- **bff-water-planning** holds the only weekly *implementation lineage*
  (`weekly_demand_calculator{,_v2,_v2_updated}.py`) — but the wired original imports
  `services.calculation_engine` and `utils.date_utils`, **which have never existed in git
  history** (verified `git log --all`), so the service cannot even boot
  (`main.py:19` → `ModuleNotFoundError`). `_v2` likewise fails on a never-committed
  `db.database`; `_v2_updated` is a method-patch fragment, not a module. Two additional
  scheduler modules (`weekly_scheduler.py`, `weekly_accumulation_scheduler.py`) have zero
  consumers and also fail to import.
- **ros-gis-integration** has the pipeline plumbing (scheduler loop, HTTP integration
  client, sits on the `ros_gis` schema) but its client posts demands to the *scheduler*
  service, not flow-monitoring's `/api/v1/control/demands`, its `base_urls` omits the
  `gis`/`ros` keys it dereferences (KeyError), and its daily calculator silently fabricates
  plots on any query failure (re-review finding #10).
- **flow-monitoring** owns the consuming contract (`POST /api/v1/control/plan`, and the
  future `/control/demands` of PR 2.4) and the hydraulic core; it must not also produce
  demand.

## Decision

1. **ros-gis-integration owns demand production** (weekly + daily): it computes demand
   records per the PR 2.4 contract (immutable/versioned, provenance, idempotency keys) and
   POSTs them to flow-monitoring `/api/v1/control/demands`. Implementation = **PR 2.6**
   (RID-gated on the crop register; technical prerequisites: 2.4 contract, 2.5 section
   master, 2.5b parcel membership).
2. **bff-water-planning is read-only for demand**: it serves GraphQL/REST views over
   `ros_gis` tables to the frontend and keeps its ROS sync + daily scheduler surfaces, but
   produces no canonical demand records. Its dead weekly-calculator stack is **deleted in
   PR 2.6a** (unrecoverable: the imports were never committed; git history retains the
   files for reference).
3. **flow-monitoring stays consumer-only**: hydraulic feasibility, aggregation, and gate
   planning; rejects stale/synthetic/non-conformant demand by contract (2.4).

## Rationale

- ros-gis-integration already runs the scheduler/client infrastructure and owns the
  `ros_gis` schema access path — the shortest honest route to a production producer.
- The BFF's mandate (backend-for-frontend) argues against it owning pipeline writes; its
  "implementation" was unbootable scaffolding, not a working producer.
- Keeping production out of flow-monitoring preserves the Wave-0/1 separation: pure
  hydraulics in `core/`, I/O at the edges, one source of truth per concern.

## Consequences

- **PR 2.6a (now):** bff boot restored by unwiring/deleting the dead weekly stack; test
  harness fixed so `pytest tests/unit/` is a real gate; no behavior change for the BFF's
  live read paths.
- **PR 2.6 (RID-gated):** producer built in ros-gis-integration: fix
  `integration_client.base_urls`, repoint from the scheduler to `/control/demands`, remove
  the fabricate-on-failure fallback (finding #10), contract tests against 2.4.
- If the maintainer overturns this ADR toward the BFF, 2.6a is unaffected (the deleted
  stack was unrunnable either way); only 2.6's target service changes.
