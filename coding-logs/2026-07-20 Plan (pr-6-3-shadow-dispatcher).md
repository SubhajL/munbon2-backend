# PR 6.3 — Scheduler shadow dispatcher & readback reconciliation (SYNTHESIS PLAN)

**Service:** `services/scheduler` (Python 3.11 / FastAPI / SQLAlchemy async / PyJWT). Gate: `PYTHONPATH=src pytest -q`.
**Method:** g-planning (Claude plan + independent Plan-agent 2nd opinion, Codex out of tokens) → this synthesis. **The two plans converged on every major decision.**
**Baseline:** main `c3d13685`. Deps: 5.2 ✅, 6.2 ✅, 6.1b ✅.

## DECISION: SPLIT into 6.3a + 6.3b
6.3 is "two PRs wearing one number," separated by a hard trust/data boundary the spec itself concedes ("deps … 6.1b **for real gates**"):
- **6.3a — shadow dispatch / validate / receipt core (scheduler-only, NO SCADA change, NO D6).** Fully implementable today against 6.2's validate endpoint. Owns done-gate tests `test_dispatch_retry_persists_one_receipt` + `test_shadow_dispatcher_has_no_execute_url`.
- **6.3b — readback reconciliation (2-service: SCADA service-authed readback endpoint + scheduler reconcile; D6-gated).** Owns `test_readback_mismatch_holds_plan` (via an INJECTED readback, actuation-independent). Implemented after 6.3a merges.

Both implemented to complete "6.3", PR-by-PR (matches 5.2a/b, 6.2a/b).

## Cross-cutting decisions (both plans agreed)
1. **Readback trust: service-authed SCADA endpoint (6.3b), NEVER operator-token minting.** Minting a viewer operator token with the shared operator `jwt_secret_key` gives the scheduler the entire operator WRITE-API blast radius — a trust inversion `service-auth.ts` exists to prevent. The scheduler holds ONLY the dedicated service token. (Also: `GET /api/gates/:id/status` is operator-authed AND returns register `1..4`, not machine `target_level 0..65535` — wrong auth AND wrong namespace.)
2. **Externally-driven `run_shadow_dispatch_once()` tick + `python -m` entrypoint. NO in-process asyncio loop.** `main.py` lifespan has no background-task/graceful-shutdown infra (shutdown is a log-only no-op); an in-process loop would be the first and would race DB-pool teardown / leak tasks. The "loop" is the external supervisor (PM2/systemd/cron). Restart-safe by idempotency.
3. **Exactly-once receipt over at-least-once dispatch:** persist keyed on `intent_id` PK via `INSERT … ON CONFLICT (intent_id) DO NOTHING`, ONLY after SCADA returns a 200/409-with-body. On 503/timeout persist NOTHING → next tick re-dispatches → SCADA idempotent-replays the byte-identical receipt → ON CONFLICT no-op. `idempotency_key` UNIQUE is a second backstop.
4. **Never-execute is STRUCTURAL:** the SCADA client builds only a module-const `_VALIDATE_PATH`, exposes exactly one network method, and a base-URL validator REJECTS any embedded path (can't smuggle `/api/gates/:id/command-level`). `test_shadow_dispatcher_has_no_execute_url`.
5. **Dark-by-default / fail-closed:** unset SCADA URL → dark; unset `SCHEDULER_SERVICE_JWT_SECRET` → cannot mint → dark (mirrors SCADA's own 503-dark); `control_execution_mode != "shadow"` → dark. A present service secret is validated by the SAME strength checks as the operator secret (extract shared `assert_strong_secret`).
6. **Token mint (`iat` is load-bearing):** HS256, `iss`=munbon-scheduler, `aud`=munbon-scada-machine-boundary, `sub` non-blank, `type:"service"`, **`iat` MANDATORY** (jsonwebtoken's `maxAge` measures from `iat` — omit it and SCADA throws), `exp = iat + min(max_age, 300)`, NO roles, signed with the DEDICATED service secret (never `jwt_secret_key`). Mint FRESH per call (never cache near the 5m boundary).
7. **Echoed-field re-verification:** the returned receipt's `intent_id`, `idempotency_key`, `intent_content_hash` MUST echo the outbox row → `ScadaContractViolation` on mismatch (mirrors `control_flow_client`).

## 6.3a — files
ADD (`services/scheduler/`):
- `src/core/service_token.py` — `mint_scheduler_service_token(*, secret, issuer, audience, subject, now, max_age_seconds=300) -> str` (pure; NOT in verify-only `auth.py`).
- `src/services/clients/scada_validation_client.py` — `ScadaValidationClient` (injectable `httpx.AsyncClient`, module `_TIMEOUT`, `token_provider` mints fresh per call, `_VALIDATE_PATH` const, single `validate_intent` method).
- `src/services/clients/scada_client_errors.py` — `ScadaUnavailableError`(503) / `ScadaServiceAuthError`(401) / `ScadaIntentRejectedError`(422) / `ScadaContractViolation`(502).
- `src/services/shadow_dispatch_service.py` — `ShadowDispatchService.run_shadow_dispatch_once`, `dispatch_validation_intent`.
- `src/jobs/shadow_dispatch_once.py` — `python -m` entrypoint (build repo+client+service, iterate active shadow plans).
- `migrations/0010_shadow_dispatch_receipts.up.sql` / `.down.sql`.
- tests: `tests/unit/test_service_token.py`, `test_scada_validation_client.py`, `test_shadow_dispatch_service.py`, `tests/integration/test_shadow_dispatch_postgres.py`, extend `test_config.py`.
CHANGE:
- `src/core/config.py` — dark-default settings (`scheduler_scada_base_url: Optional[str]=None`, `scheduler_service_jwt_secret: Optional[str]=None`, `_issuer="munbon-scheduler"`, `_audience="munbon-scada-machine-boundary"`, `_max_age_seconds=300`, dispatcher knobs); extract `assert_strong_secret` shared by both secret validators.
- `src/models/control_plan.py` — ORM `ControlCommandValidationReceipt` (drift-locked).
- `src/repositories/control_plan_repository.py` — `load_dispatchable_intents()` (claimed ∧ ¬missed/invalidated ∧ ¬receipted ∧ deadline-not-passed) + `record_validation_receipt()` (ON CONFLICT DO NOTHING → bool inserted) + DTOs.
- `src/api/v1/endpoints/control_plans.py` — OPTIONAL `POST .../dispatch-once` (require_supervisor) that calls run_shadow_dispatch_once (thin; the tested surface is the pure fn + CLI).

## 6.3a — migration 0010 (append-only, immutable, exactly-once)
`scheduler.control_command_validation_receipts`: PK `intent_id` (one receipt per intent); UNIQUE `idempotency_key`; FK `(plan_id,plan_version)→control_plan_runs ON DELETE RESTRICT` (NO outbox FK — additive-independent like 0009); cols receipt_id/correlation_id/request_id/intent_content_hash/capability_hash/status/reason_code/validated_at/`receipt_document_text`(verbatim)/`receipt_content_sha256`/dispatch_worker_id/dispatched_at/created_at; CHECK status∈{accepted,rejected}; CHECK accepted⇒reason NULL & rejected⇒reason NOT NULL; CHECK reason_code vocab = the 8 frozen reasons; reuse the 0001 `control_plan_rows_are_immutable()` trigger (drift test requires the trigger on append-only tables). Down = clean DROP (purely additive). ORM must mirror EXACTLY (`test_control_models_match_migration_ddl.py`).

## 6.3a — dispatch flow (status mapping)
`run_shadow_dispatch_once`: `dark` unless mode==shadow AND SCADA client configured → (1) `advance_open_loop_execution` (5.2's ONE claim path — do NOT re-claim), (2) `load_dispatchable_intents`, (3) `dispatch_validation_intent` each. `dispatch_validation_intent`: `json.loads(row.intent_document_text)` → `validate_intent` →
- **200 (accepted OR rejected)** → validate receipt mirror + echoed-field re-verify → `record_validation_receipt` ON CONFLICT DO NOTHING. `validation_rejected` IS persisted (it's a successful validation; SCADA returns 200).
- **409 idempotency_conflict** → record failure, NOT a success row.
- **422 schema_invalid** → scheduler compile bug; fail loud, no receipt.
- **503 / RequestError / timeout** → persist NOTHING; retry next tick.

## 6.3a — test list (name — behavior)
- `test_dispatch_retry_persists_one_receipt` (done-gate) — dispatch twice (idempotent replay) → exactly one row, byte-identical doc; + concurrent-ticks PK-conflict variant (integration).
- `test_shadow_dispatcher_has_no_execute_url` (done-gate) — only `/command-intents/validate` built; no command-level/horn/execute/actuate literal; no execute config knob; base-URL-embedded-path rejected.
- mint token has the SCADA-accepted shape (iss/aud/sub/type=service/exp/iat within maxAge, no roles, service secret not operator secret); wrong-aud/missing-iat/wrong-type rejected by a Python verifier proxy.
- 200-rejected persisted as success; 409 not persisted; 503 persists nothing then a later 200 persists one; echoed-hash mismatch → contract violation, nothing persisted.
- dark without SCADA url / without service secret / when mode disabled — nothing dispatched.
- `load_dispatchable_intents` excludes unclaimed/missed/invalidated/receipted/past-deadline.
- integration (disposable loopback PG): 0010 apply/rollback/reapply; full claim→dispatch→persist; restart re-run → identical receipts, zero new rows.
- config: service-secret dark default None; weak service secret rejected.

## 6.3b — outline (after 6.3a merges)
- SCADA: `GET /internal/v1/gates/:canonical_gate_id/readback` (same `requireServiceAuth`; dark when secret unset) projecting the gate snapshot into machine-boundary terms via the 6.1b artifact.
- Scheduler: `ScadaReadbackClient`, `reconcile_gate_readback(observed, expected_baseline, tolerance) -> verdict` (drift vs the plan's BASELINE world-model, NOT the target — non-vacuous under no-actuation), config-gated (off|observe|enforce, default observe), migration 0011 `control_gate_readback_observations` + ORM, hold via existing `hold_control_plan`. Done-gate `test_readback_mismatch_holds_plan` with injected readback. Baseline sourcing (config vs captured-at-activation) is a documented open question — a further reason 6.3b is D6-gated.

## Risks / scope-creep guards
- Do NOT relax the 0009 event_type CHECK to add validated/dispatched — the receipt lives in NEW 0010.
- Do NOT build the SCADA readback endpoint / reconciliation / in-process loop / metrics (6.4) into 6.3a.
- Namespace trap [6.3b]: machine target_level 0..65535 vs Waste-Way register 1..4 — reconcile via the 6.1b artifact, never assume equality.
- Everything dark-by-default; revert = unset envs / drop 0010.
