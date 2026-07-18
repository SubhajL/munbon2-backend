# PR 4.4a-2 — control-plane runtime + truthful readiness (impl log)

**Date:** 2026-07-18 · **Base:** main `69aa100f` (post-4.4a-1) · **Branch:** `feat/control-plane-runtime-readiness`
**Plan:** `coding-logs/2026-07-18 Plan (pr-4-4a-4-4b-control-plane-hardening).md` (sub-PR 4.4a-2). Scheduler + flow + bff + infra.

## What shipped
- **Canonical scheduler port 3021**: `start.sh` honors `$PORT` default 3021 (was hardcoded 3012); PM2 scheduler `PORT:'3021'`+`port:3021`; config default 3021; BFF/ros already 3021. Flow stays 3011, bff 3002.
- **`.env` sourcing is now FALLBACK-ONLY** (both start.sh): a PM2/host-injected var (`PORT`, `POSTGRES_URL`, …) is authoritative and never clobbered by a stale `.env` (bash `${!_key+x}`). Fixes the deploy bug where `.env PORT=3012` overrode PM2's 3021, and where migrate + runtime could target different DBs.
- **Runtime DB URL unified with migration**: `core/config.py database_url` = `AliasChoices("POSTGRES_URL","DATABASE_URL")` (POSTGRES_URL preferred) so runtime serves the same DB migrations apply to.
- **`apply-all` migration verb** (both migrate.py): `discover_migration_ids()` (reject half-pairs; lexical == numeric at 4-digit ids) + `apply_all_migrations()` (idempotent, per-pair advisory-lock + checksum, aborts before later pairs on drift). Kept apply/rollback/status.
- **Migrate-before-start**: both `start.sh` run `migrate.py apply-all || exit 1` then `exec uvicorn` — PM2 never boots a half-migrated / falsely-ready process (unset POSTGRES_URL blocks boot = intended fail-closed).
- **Flow release wired**: PM2 flow `HYDRAULIC_MODEL_RELEASE_PATH=data/model-releases/engineering-prior-v3-v1.json` (verified `commandable:false`/`evidence_class:engineering_prior`; asserted in pm2 test). Loader/flags untouched.
- **Retired** `.github/workflows/deploy-flow-monitoring.yml` (no tracked Dockerfile; PM2 is the topology) + removed its stale path triggers from `flow-monitoring-tests.yml`.
- **Readiness split**: `/health` = process liveness ONLY (bff lost its hardcoded `external_health:True`; reports real 2.0.0). `/ready` = dependency truth, 503 on any failure, no host/cred/exception leaks:
  - Scheduler `core/readiness.py`: tracked migration ids+checksums vs `scheduler.schema_migrations` + 5 control tables `to_regclass` + Redis ping; missing/extra/drift/empty-baseline → 503.
  - Flow `core/readiness.py`: PostgreSQL probed DIRECTLY (`postgres.ping()` under `asyncio.timeout`, not the multi-store `check_health`) + valid commandable=false release + prediction service + both prediction tables + migration checksum + baseline present.
  - BFF `services/readiness_service.py`: bounded concurrent probes of scheduler `/ready` + flow `/ready` + ros `/health`, each under a per-probe `asyncio.timeout` WALL-CLOCK; per-target `expected_status` (scheduler/flow=`ready`, ros=`healthy` — liveness is NOT accepted as readiness); a missing/closed pooled client → 503.
- **BFF pooled client**: one lifespan-owned `httpx.AsyncClient` reused by projection reads AND probes; cleanup in `try/finally`; removed duplicate `scheduler_service_url`; added probe timeout + wall-clock settings.

## Gate
scheduler **379 passed / 6 skip**, flow **1281 / 10**, bff **101**, infra pm2 **16** — each ×3, no new skips, nothing weakened. pyflakes clean on changed files (the 2 unused imports in bff main.py are pre-existing on origin/main).

## 2-tier QCHECK (both tiers; all findings fixed + regression-tested)
- Tier-1 (Opus adversarial): 1 HIGH — scheduler `start.sh` `.env` clobbers PM2 `PORT` (green text-grep test masked it); 2 LOW.
- Tier-2 (Codex gpt-5.6-sol high): escalated to CRITICAL (same `.env` clobber ALSO splits migrate-DB vs runtime-DB) + HIGH probe-not-wall-clock (slow-drip hang) + HIGH liveness-accepted-as-readiness + 3 MED (readiness exceptions→500; flow pings unrelated stores; empty manifest passes) + 1 LOW (client cleanup). All 7 fixed with behavioral regression tests (the port test now runs the REAL start.sh block under bash).

## ⚠️ Incident (surfaced to user; not a code defect)
During impl the agent's manual `migrate.py apply-all` verification (with `env -u POSTGRES_URL`, which `load_dotenv` overrode) applied scheduler migrations 0001/0002/0003 to the LIVE shared remote `43.208.201.191/munbon_dev`. Additive/empty/idempotent (the intended 4.4a external cutover op) — NOT rolled back (a DROP on a live shared DB is a worse mutation). Test gates never touch a DB. External: rotate the E1 credential; manage that DB's state within the controlled cutover.

## External ops (documented, not executed)
Update the deployed `.env`/host env to a strong JWT secret + issuer/audience/mode (4.4a-1) and to a single canonical `POSTGRES_URL` (the tracked `.env` currently has POSTGRES_URL and DATABASE_URL on different hosts — now unified in code, but the real env should be cleaned); apply migrations to the remote via the controlled cutover; restore E6 CI billing.
