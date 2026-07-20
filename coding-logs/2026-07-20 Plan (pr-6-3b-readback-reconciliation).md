# PR 6.3b — Readback reconciliation (PLAN)

**Split from PR 6.3** (6.3a = dispatch core, merged #96). 2-service (SCADA + scheduler), D6-gated.
**Design source:** the 2-opinion 6.3 synthesis (`coding-logs/2026-07-20 Plan (pr-6-3-shadow-dispatcher).md`) + this refinement against the actual SCADA readback source. **Baseline:** main `96c0cdc9`.

## Reality check (drives the scope)
- SCADA readback is a discrete **level 1..4** (`GateSnapshot.gateLevel.value.level` / `.raw`), keyed by the ONE polled site gate — NOT a continuous position, and NOT keyed by canonical_gate_id.
- D6 is UNAVAILABLE → the 6.1a device-capability snapshot is the empty dark default (zero machine-capable gates), so a machine-boundary readback endpoint returns `{gates: {}}` by default.
- Under SHADOW (no actuation) the gate never moves to the intent target, so "readback ≠ target ⇒ hold" is VACUOUS. The non-vacuous predicate is **drift vs the plan's BASELINE** (the level the plan believes the gate holds), not the target.

## Decisions
1. **Reconciliation semantics (non-vacuous under no-actuation):** `reconcile_gate_readback(observed_level, expected_level, observed_quality) -> verdict ∈ {ok, mismatch, stale, unavailable}`. A `mismatch` (observed_level != expected_level, both fresh) means a competing actor / manual move / sensor fault invalidated the open-loop plan's starting assumptions → hold. `stale`/`unavailable` never hold (can't confirm — don't act on bad data). PURE.
2. **Baseline sourcing:** the `expected_level` is INJECTED (a per-reconcile input the caller supplies) — actuation-independent + deterministic for the done-gate test. Real-ops baseline (config vs captured-at-activation) is DEFERRED/documented — activation (4.3c) captures no readback (dark, D6 unavailable), so there is no captured baseline yet. 6.3b builds the MECHANISM; the baseline source lands with D6.
3. **Config-gated (dark-by-default):** `control_readback_reconciliation_mode ∈ {off, observe, enforce}` default **off**. off → no reads (dark). observe → read + record an observation, NEVER hold. enforce → read + record + hold on `mismatch` via 5.2's `hold_control_plan` (a plan-level `held` event; keeps authority — a hold is NOT a lifecycle exit).
4. **Readback trust = service auth (NOT operator).** SCADA `GET /internal/v1/gate-readback` guarded by the SAME `requireServiceAuth` as the validate endpoint (dark 503 when `SCHEDULER_SERVICE_JWT_SECRET` unset). The scheduler holds ONLY the service token — never operator creds.
5. **No actuation** anywhere (both services).

## SCADA side
- `api/internal-routes.ts`: `GET /internal/v1/gate-readback` (requireServiceAuth, `Cache-Control: no-store`). Projects the live gate snapshot into machine-boundary readback for machine-capable gates: `{capability_release_id, capability_hash, observed_at, gates: {canonical_gate_id: {device_id, adapter_gate_id, observed_level|null, quality}}}`. A machine-capable gate is mapped to the live poll iff its `canonical_gate_id` equals the NEW optional `SCADA_SITE_CANONICAL_GATE_ID` (the polled site gate's canonical id); otherwise `observed_level:null, quality:'unavailable'`. Dark/empty capabilities → `gates: {}`. NO actuator/transport/write. Add `snapshot` (already in ApiDeps) + the site-canonical-gate config to `InternalDeps`.
- `domain/gate-readback.ts` (pure): `projectGateReadback(deviceCapabilities, snapshot, siteCanonicalGateId, now)` → the readback map. Tested pure.
- Config: `SCADA_SITE_CANONICAL_GATE_ID` (optional; unset → every machine gate is `unavailable`).

## Scheduler side
- `core/readback_reconciliation.py` (pure): `reconcile_gate_readback(observed_level, expected_level, observed_quality) -> ReadbackVerdict`.
- `services/clients/scada_readback_client.py`: `ScadaReadbackClient.get_gate_readback(token) -> GateReadbackSnapshot` (mirrors the validation client — injectable transport, module-const `_READBACK_PATH`, fail-closed status map, contract validation). Reuses the service-token minter.
- `services/readback_reconciliation_service.py`: `reconcile_plan_readback(session, plan_id, plan_version, expected_levels, now)` — dark unless mode != off; reads readback (or takes an injected one for tests), reconciles each active gate, records observations, and on `mismatch` in ENFORCE mode calls `hold_control_plan`. Returns a report.
- Migration **0011** `control_gate_readback_observations` (append-only, immutable, drift-locked): `(observation_id PK, plan_id, plan_version, canonical_gate_id, observed_level, expected_level, quality, verdict, reconciliation_mode, observed_at, created_at)`, FK→control_plan_runs, reason/verdict CHECK. + ORM.
- Config: `control_readback_reconciliation_mode` (default `off`) + `scheduler_scada_base_url` reused for the readback client.

## Tests
- SCADA: `projectGateReadback` — empty capabilities → `{}`; a machine gate matching the site canonical id → live level projected; a non-matching gate → `unavailable`; dark endpoint 503 (no service secret); operator token → 401 (service-authed); service token → 200; no-store.
- Scheduler: `reconcile_gate_readback` — ok when observed==expected; mismatch when differ (fresh); stale/unavailable never mismatch. `test_readback_mismatch_holds_plan` (done-gate) — enforce mode + injected observed!=expected → a `held` event appended + claiming paused; matching → no hold; observe mode → observation recorded, NO hold; off → dark (no read, no hold). Migration 0011 apply/rollback/immutability on disposable PG. Client status mapping via MockTransport.

## Wiring / dark path
SCADA: endpoint dark 503 unless service secret set; empty gates unless capabilities + site canonical id set. Scheduler: `control_readback_reconciliation_mode=off` (default) → the service reads nothing and holds nothing (byte-identical to no-6.3b). Everything fail-closed.

## Risks
- Namespace: machine `target_level 0..65535` vs Waste-Way register `1..4` — reconcile LEVELS as-is (both are the discrete register value for this gate); document that a real multi-device D6 mapping is needed for the general case.
- Baseline sourcing is injected/deferred (documented) — no spurious holds because default mode is off and stale/unavailable never hold.
- Hold is reversible (5.2 resume) and keeps authority (not a lifecycle exit).
