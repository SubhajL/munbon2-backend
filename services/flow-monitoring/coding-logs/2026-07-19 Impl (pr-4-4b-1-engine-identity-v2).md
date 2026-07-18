# PR 4.4b-1 — Flow prediction-engine identity v2 (impl log)

**Date:** 2026-07-19 · **Base:** main `ecada6ea` (post-4.4a) · **Branch:** `feat/flow-engine-identity-v2`
**Plan:** `coding-logs/2026-07-18 Plan (pr-4-4a-4-4b-...).md` (4.4b engine-identity). First of the 4.4b split (b-1..b-4).

## What shipped
- **Content-hashed prediction-engine descriptor** (NEW `core/prediction_engine.py`): `build_prediction_engine_descriptor(source_root)` hashes a FIXED-ORDER manifest of the 12 prediction-closure files (raw bytes, domain-separated) → `build_digest`; descriptor = {schema_version 1, engine_id, semantic_contract_version, build_digest, content_hash}. `load`/`validate` reject missing/extra/malformed/hash-drift. Deterministic from file bytes alone (no git/branch/mtime/cwd). Generator `scripts/build_prediction_engine_descriptor.py` (+ `--check` gate) + committed `data/prediction-engine/prediction-engine-v1.json`.
- **Snapshot v3** (`core/model_snapshot.py`): embeds the descriptor in the hashed payload BEFORE `snapshot_id = content_hash(payload)`, so an engine change moves the snapshot id (and thus the prediction identity).
- **Identity v2** (`core/prediction_repository.py`): `prediction_run_id_for(payload, identity_version)` — the v1 prefix + `canonical_json_bytes` are BYTE-FROZEN (existing runs replay identically); a new `…:v2\n` prefix domain-separates v2. `PredictionRunRecord` gains identity_version + engine pins; `__post_init__` validates the full embedded descriptor shape then pins the columns to it + re-derives the run id.
- **Rollout** (`api/control.py`): `accept-v1-write-v2` (default) — fresh writes always identity_version=2, legacy v1 rows replay by their frozen v1 id; `require-v2` — the caller MUST pin `X-Prediction-Engine-Content-Hash` == the current descriptor content_hash (fail closed otherwise). No new-v1 write path. Artifact + identity/engine response headers on POST + GET.
- **Migration 0002_prediction_engine_identity_v2**: additive NULLABLE engine columns; identity CHECK relaxed to IN(1,2); v2-requires-engine + v1-requires-NULL CHECKs; down refuses if any identity_version=2 row exists; reuses the 0001 immutability trigger; drift-lock covers both pairs.

## Gate
flow **1317 passed / 13 skipped** (baseline 1281+10; +36 tests, +3 env-gated Postgres skips) — ×3, nothing weakened. pyflakes clean. descriptor `--check` green. Migration + v1/v2 roundtrips proven on a DISPOSABLE loopback Postgres (never the live remote).

## 2-tier QCHECK (both tiers; the tiers DISAGREED on severity — adjudicated)
- Tier-1 (Opus adversarial): empirically verified v1-freeze / determinism / engine→identity-before-hash / rollout fail-closed / 0001→0002 relaxation on a loopback PG; 1 MED (the 0002 NULL-in-CHECK) + 2 LOW.
- Tier-2 (Codex gpt-5.6-sol high): 3 HIGH (drift-warns-not-fails / require-v2-no-client-pin / 0002 NULL-in-CHECK) + 1 MED (embedded descriptor unvalidated).
- **4 fixes applied + regression-tested:** (1) migration 0002 v2 CHECK now guards `build_digest`/`content_hash` with `IS NOT NULL` before the regex (the SQL NULL-in-CHECK gotcha — Codex+Opus agreed, Opus confirmed on PG15); (2) descriptor drift from live source → descriptor UNAVAILABLE → fresh v2 / require-v2 / model-snapshot fail closed (no serving a false engine identity); (3) require-v2 requires the explicit `X-Prediction-Engine-Content-Hash` client pin == current (kept OUT of the frozen identity payload); (4) `__post_init__` runs the full descriptor validator on the embedded block (rejects schema 999 / extra keys / drifted content_hash). **Declined:** cursor-N/A; `.gitattributes eol=lf` (Mac/Linux-only deploy, autocrlf unset — low-risk, documented).

## External ops (documented, not executed)
Apply flow migration 0002 to the remote via the controlled cutover; before enabling `require-v2` (end-state), upgrade callers to send the engine content-hash header; the `--check` re-pin gate must run on any prediction-closure edit.
