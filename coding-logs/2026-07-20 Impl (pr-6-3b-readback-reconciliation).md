# PR 6.3b — Readback reconciliation (IMPL LOG)

**Branch:** `feat/6-3b-readback-reconciliation` off `origin/main` (`96c0cdc9`). **2-service** (scheduler Python + SCADA TS). Completes the split PR 6.3 (6.3a = dispatch core, #96).
**Plan:** `coding-logs/2026-07-20 Plan (pr-6-3b-readback-reconciliation).md` (2-opinion 6.3 synthesis + SCADA-source refinement).
**Gates:** scheduler `PYTHONPATH=src pytest -q` **769 passed** (incl. disposable-PG :55443 integration; 6.3b subset 3× clean; pyflakes clean); SCADA `npm run typecheck && npm run lint && npm test` **371 passed** ×3, build clean.

## What shipped (config-gated, dark-by-default, NO actuation, SERVICE-authed)
Under SHADOW there is no actuation, so the non-vacuous check is DRIFT vs the plan's BASELINE (the level the plan believes a gate holds), NOT the intent target. The mechanism is fully built + tested with an INJECTED readback (actuation-independent); the real baseline source is D6-gated.

**Scheduler:**
- `core/readback_reconciliation.py` — pure `reconcile_gate_readback(observed_level, expected_level, observed_quality) -> {ok, mismatch, unavailable}`: `unavailable` when null level OR quality != 'ok' (NEVER a hold — acting on unreliable data would spuriously pause); else ok/mismatch on level equality.
- `services/readback_reconciliation_service.py` — `reconcile_plan_readback`: mode `off` → dark (no record/hold); `observe` → record one observation per baseline gate, NEVER hold; `enforce` → record + HOLD the plan ONCE on any fresh `mismatch` via 5.2's `hold_control_plan` (a plan-level `held` event — reversible, keeps the authority mutex, NOT a lifecycle exit).
- `services/clients/scada_readback_client.py` — `ScadaReadbackClient.get_gate_readback` reads the SCADA endpoint with the SAME service token as the validation client (reuses `_require_hostonly_base_url` — no path/userinfo/execute smuggling); fail-closed status map (503/401/contract) + shape validation.
- Migration **0011** `control_gate_readback_observations` (append-only, immutable, verdict∈{ok,mismatch,unavailable} + mode∈{observe,enforce} CHECK, FK→runs only — independent of 0007/0009/0010) + ORM (drift-locked). `record_readback_observation` + `ReadbackObservationRow`.
- config `control_readback_reconciliation_mode` (default `off`, validated). `jobs/shadow_dispatch_once.py`: `build_readback_client` / `build_readback_reconciliation_service` / `reconcile_active_plans` wired into `main()` — DARK unless mode != off; baselines are D6-gated → empty → no-op.

**SCADA:**
- `domain/gate-readback.ts` — pure `projectGateReadback(snapshot, gate, siteCanonicalGateId, observedAtIso)`: for each machine-capable gate, the LIVE poll level (`gateLevel.raw`) iff its canonical_gate_id == `SCADA_SITE_CANONICAL_GATE_ID`, else `observed_level:null, quality:'unavailable'`; empty (dark) capabilities → `{}`. `Object.fromEntries` (pollution-safe).
- `GET /internal/v1/gate-readback` (`internal-routes.ts`) — `requireServiceAuth` (dark 503 when service secret unset; SERVICE-authed, NOT operator — a 401 for an operator token is tested), `Cache-Control: no-store`, read-only (no actuator/transport). `SCADA_SITE_CANONICAL_GATE_ID` config; `siteCanonicalGateId` threaded through `ApiDeps`.

## Done-gate + verification
`test_readback_mismatch_holds_plan` (scheduler unit): enforce mode + an injected observed!=expected baseline → a real 5.2 `held` event + report.held. Also proven on real Postgres: migration 0011 applies + append-only (UPDATE/DELETE rejected); an enforce reconcile of a drifting readback records a `mismatch` observation (0011) AND appends a `held` event (0009). SCADA: endpoint dark 503 without service secret; operator token → 401; service token → 200 with the projected readback (empty by default; live level when the site gate is configured); no-store.

## Dark path
Scheduler `control_readback_reconciliation_mode=off` (default) → main() builds no readback client, makes no SCADA call, records nothing, holds nothing (byte-identical to no-6.3b). SCADA readback endpoint dark 503 unless the service secret is set; empty gates unless capabilities + `SCADA_SITE_CANONICAL_GATE_ID` set. Everything fail-closed.

## Deferred (documented)
Baseline sourcing (config vs captured-at-activation) is D6-gated — activation captures no readback (dark), so the driver reconciles nothing until real per-gate baselines exist. The register-level (1..4) vs machine target_level (0..65535) namespace is reconciled as-is for the single Waste-Way gate; a general multi-device D6 mapping is future work.

## 2-tier QCHECK — NO CRITICAL, NO HIGH (both tiers)
Tier-1 `/code-review high` (workflow, 19 agents, 0 errors) + Tier-2 Opus 4.8 adversarial (Codex out of tokens; developer-feedback prompt). Both verified all four safety claims (drift-not-target, `unavailable`-never-holds, genuinely dark-by-default, service-auth separation — Opus confirmed the operator-token-401 test + the fresh-quality guarantee). The two tiers **strongly correlated** on operability. Resolutions:
- **[both, M1] the enforce hold re-fired every tick** (docstrings said "once", code was once-per-tick) → unbounded `held`/observation rows + silently reverting an operator resume. FIXED: check `is_plan_held(context.events)` before holding — hold only if not already held (a resume with the drift still present re-holds next tick). +test (already-held plan → no re-hold, observation still recorded).
- **[both, M2] a readback outage crashed the WHOLE dispatch tick** (`get_gate_readback` was before the per-plan try/except, `main()` had no except). FIXED: `reconcile_active_plans` short-circuits when `baselines` is empty (NO SCADA poll until D6 baselines exist), guards `get_gate_readback` (log + skip on `ScadaClientError`), and `main()` wraps reconciliation as a best-effort sidecar that can never fail the (already-committed) dispatch tick. +tests (short-circuit-no-SCADA-call, readback-outage-isolated).
- **[tier-1 [99], sharper than tier-2 L1] observation commits BEFORE the hold** → a hold failure (esp. the plan concurrently invalidated → `HoldNotAllowedError`) left a `mismatch` observation with no hold. FIXED: catch `HoldNotAllowedError` (the plan is ALREADY terminal → not fail-open) + documented the non-atomicity as a benign one-tick window (dispatch is validation-only, nothing actuates; the next tick re-attempts).
- **[both, M3] baseline namespace under-specified** (readback 1..4 vs machine target_level 0..65535) — a forward footgun (no current bug; baselines empty). FIXED: pinned the contract prominently in the pure-fn + service docstrings (`expected_level` MUST be the discrete gate-level, NOT target_level).
- **[tier-2 N1] readback client imported the validation client's PRIVATES.** FIXED: extracted `services/clients/scada_http.py` (`require_hostonly_base_url` + `SCADA_TIMEOUT`, public) — both clients now import it (killed the private cross-module import + the fork).
- **[tier-2 L3] no DB↔Python vocab-parity test for 0011.** FIXED: added a test tying the verdict/mode CHECK to the `VERDICT_*`/`MODE_*` constants.
- **DEFERRED (documented, moot while dark):** [tier-1 [73]] per-gate observation commits (batch when D6 multi-gate lands; K=1 today), [tier-1 [146]] the reconcile re-loads active plan keys (never runs while baselines empty — the short-circuit returns first), [both L2/[103]] `hold_control_plan` drops `actor_subject` (pre-existing 5.2; the `reason` field records "readback drift on gates …"), [tier-2 L4/N2] client trusting the quality string / silent all-unavailable on a mis-set site gate (fail-safe: at worst a spurious reversible hold).

Post-fix gate: scheduler full suite **773 passed**, 6.3b subset **3× clean**; SCADA **371 passed** (typecheck/lint clean; unaffected by the scheduler fixes); pyflakes clean. The 6.3a validation-client tests stay green after the shared-helper extraction.
