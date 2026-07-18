# PR 4.4b-3 — bounded control-plan read projections (impl log)

**Date:** 2026-07-19 · **Base:** main `9c9952cd` (post-4.4b-2) · **Branch:** `feat/scheduler-bounded-projections`
**Plan:** `coding-logs/2026-07-18 Plan (pr-4-4a-4-4b-...).md` (4.4b bounded-projections). Third of the 4.4b split. No migration.

## What shipped
- **Scheduler dedicated bounded read projections** (`PostgresControlPlanProjectionRepository`): `load_prediction_coverage`, `load_lifecycle_history`, `load_ledger_projection` — each a SINGLE-plan-snapshot query selecting only the columns the projection needs, NEVER `_assemble`, NEVER a run-level large document (optimizer_result / model snapshot / canonical input / prediction request / prediction RESPONSE — and for v2 never `prediction_response_document_text`). New endpoints `GET .../prediction-coverage` + `.../lifecycle-history` (`require_operator`); the `.../ledger` endpoint switched from the `_assemble` service path to `load_ledger_projection`. Detail (`GET .../versions/{v}`) still uses `_assemble` (exact). Each read re-verifies the hashes it loads; corruption → 503, absent → 404.
- **BFF**: `get_prediction_coverage`/`get_lifecycle_history` now call the dedicated scheduler endpoints (new `SchedulerClient` methods, same fail-closed taxonomy incl. 4.4b-2 400/422→BadRequest) instead of projecting from the full detail. Strict `extra="forbid"` mirrors unchanged. Deployment ordering: scheduler before BFF (no feature flag).

## Gate
scheduler **490 passed / 16 skipped** (baseline 459+14; +31 tests, +2 env-gated Postgres skips), bff **142** — each ×3, nothing weakened. pyflakes clean. Bounded-vs-`_assemble` EQUIVALENCE proven on a DISPOSABLE loopback Postgres (v1 + v2). Boundedness proven by compiled-SQL assertions.

## 2-tier QCHECK (the tiers DISAGREED HIGH-vs-LOW — adjudicated from the code)
- Tier-1 (Opus adversarial): ran the loopback equivalence test (bounded ≡ detail, byte-identical); rated everything LOW/safe-to-merge.
- Tier-2 (Codex gpt-5.6-sol high): 2 HIGH + 3 MED + 1 LOW — the bounded reads had NARROWED the fail-closed integrity `_assemble` gave.
- **Adjudication (read the actual code):** both HIGHs were real narrowings, fixed:
  - **HIGH-1** ledger dropped the 4.3b per-row lineage guard → restored: each ledger row's `prediction_run_id` + content-sha must equal the plan header's (v2 vs `artifact_sha256`, v1 vs `prediction_response_sha256`); strict `provenance_version` dispatch (None|2, else corrupt); added `artifact_sha256` to the ledger columns. Proven by foreign-but-hash-valid-rows → 503.
  - **HIGH-2** coverage returned `prediction_member_summaries` unauthenticated → v2 now re-verifies them against the hash-pinned `coverage_summary_sha256` (a bounded component of the provenance reference); **v1 narrowing ACCEPTED + documented** (immutability triggers are the primary defense, v1 is legacy — no aggregate reload). Proven by v2 well-formed-mutation → 503.
  - **MED**: multi-statement history/ledger now pin a REPEATABLE READ snapshot (`_begin_snapshot_read`, rollback-then-set); well-formed-but-schema-invalid stored JSON → `ProjectionCorruptError` 503 not 500 (`_model_or_corrupt`); the ledger equivalence test got an INDEPENDENT hard-coded oracle (caught a `required-delivered`→`+` mutant the old builder-vs-builder oracle passed). **LOW**: ledger filters requirements to `scheduled` + events to referenced gates in SQL.
  All fixed + regression-tested; verified on a disposable loopback (live remote never touched).

## Note
The `_assemble` DETAIL path is unchanged and remains the fully-authenticated exact read. Bounded coverage/history/ledger are the go-forward optimization; v2 is provenance-sha authenticated, v1 coverage member-summary authentication relies on the append-only immutability triggers (v1 is being phased out by 4.4b-2's v2 writes).
