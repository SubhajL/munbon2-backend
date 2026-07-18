# PR 4.4b-4 — control-plan CAMPAIGN identity (impl log)

**Date:** 2026-07-19 · **Base:** main `ae813149` (post-4.4b-3) · **Branch:** `feat/scheduler-campaign-identity`
**Plan:** `coding-logs/2026-07-18 Plan (pr-4-4a-4-4b-...).md` (4.4b plan-identity). FINAL sub-PR of the 4.4b series — completes PR 4.4b. Scheduler + BFF + repo-root contracts. User DECISION: campaign_id + monotonic immutable plan_version.

## What shipped
- **Immutable campaign mapping** `migrations/0006_control_plan_campaign_identity`: NEW `scheduler.control_plan_campaign_versions(campaign_id, plan_version, plan_id)` — PK(campaign_id,plan_version), UNIQUE(plan_id,plan_version), CHECK(plan_version>0), DEFERRABLE-INITIALLY-DEFERRED FK→control_plan_runs (run + mapping commit atomically), (campaign_id) index, reused 0001 immutability trigger. Backfills every legacy run as a singleton campaign (campaign_id=plan_id) WITHOUT touching the immutable run rows. Down REFUSES once any campaign has >1 version or a non-singleton mapping (forward-fix-only).
- **`DraftControlPlanRequest.campaign_id: Optional[UUID]`** — absent → a new campaign UUID + plan_version 1; present → the campaign's `max(plan_version)+1` (a present-but-UNKNOWN campaign fails closed, never auto-creates). `allocate_campaign_version` takes a campaign-scoped `pg_advisory_xact_lock` (stable int8 key) before reading max(), so concurrent same-campaign drafts get distinct monotonic versions; the `find_by_input_hash` replay check runs FIRST so an idempotent replay consumes NO version; a failed compute/commit consumes none. `plan_id` stays a fresh per-version UUID (all routes/FKs unchanged).
- **Responses carry `campaign_id`** (detail + bounded list summary + coverage), resolved from the mapping (fail-closed 503 on a missing mapping). Supersede requires the SAME campaign AND is FORWARD-only (`successor.plan_version > record.plan_version`) + the existing physical-scope + trusted-approval rules.
- **Cross-service contract (atomic)**: the BFF strict mirrors (detail/coverage/summary) gain `campaign_id` and the shared `contracts/control-plans/v1/` schema+fixture were updated so both validators agree (`extra="forbid"` drift-detection intact; PROJECTION_SCHEMA_VERSION stays 1).
- **Readiness** (`core/readiness.py`, from 4.4a-2): `control_plan_campaign_versions` added to EXPECTED_CONTROL_TABLES + `0006` to REQUIRED_BASELINE_MIGRATION_IDS, so `/ready` 503s if the new source-of-truth table or 0006 is missing.

## Gate
scheduler **502 passed / 19 skipped** (baseline 490+16; +12 tests, +3 env-gated Postgres skips), bff **142** — each ×3, nothing weakened. pyflakes clean. Migration 0006 apply/rollback/reapply + backfill(no-rewrite) + down-refusal + a DETERMINISTIC advisory-lock contention proof (session B blocks on `pg_locks` until A commits, then sees A's committed max) all verified on a DISPOSABLE loopback Postgres (live remote never touched). v1 drafts byte-unchanged (golden pre-4.4b-4 input hash pinned).

## 2-tier QCHECK (both tiers; Codex re-run after a transient kill; all findings fixed)
- Tier-1 (Opus adversarial): empirically proved the advisory-lock serialization (deterministic contention experiment), the hash change, backfill no-rewrite, down-refusal; 1 MEDIUM + LOWs.
- Tier-2 (Codex gpt-5.6-sol high): 3 HIGH + 2 MED — uncorrelated catches. All fixed + regression-tested:
  - **HIGH (both)** `campaign_id=null` in the hashed input changed `input_content_hash` for the common path → **excluded when None** (golden pre-PR hash pinned) so pre-PR drafts still replay; a pinned campaign_id still changes the hash.
  - **HIGH (Codex)** supersede lacked the forward-only invariant → an approved v1 could retire an approved v2 for stale control → **`successor.plan_version > record.plan_version` required**.
  - **HIGH (Codex)** in-flight pre-PR writer during cutover could orphan a run → already fail-closed (mapping-less run → 503, proven); **drained-writer cutover documented** (no runtime backfill-on-read).
  - **MED** readiness now knows the table + 0006; **MED** concurrency test rewritten to DETERMINISTICALLY prove lock contention (mutation-verified); **LOW** the READ-COMMITTED requirement of allocate is documented.

## External ops (documented, not executed)
- **Drained-writer cutover**: STOP all scheduler writers before applying 0006 (migrate-before-start on the single PM2 instance satisfies this; a rolling deploy must drain first) — a legacy writer that commits a run without the atomic campaign mapping leaves a fail-closed 503 orphan; the remedy is a forward-fix mapping migration, never a runtime backfill-on-read.
- **Operator-global campaigns (conscious decision)**: any authorized operator who knows a campaign_id can append a version; only UNKNOWN campaigns fail closed. Matches design intent (drafts are non-commanding; approval has separate trust gates) — no ownership check added.
- Apply flow 0002 + scheduler 0005 + 0006 to the remote via the controlled cutover.

## PR 4.4b COMPLETE (b-1 #82, b-2 #83, b-3 #84, b-4 this) — and with PR 4.4a (#79/#80/#81) the whole control-plane hardening goal is done.
