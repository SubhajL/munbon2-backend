# PR 4.3c-1 — shadow activation core (impl log)

**Date:** 2026-07-19 · **Base:** main `92516380` (post-6.1a) · **Service:** `services/scheduler` (Python)
**Plan:** `coding-logs/2026-07-19 Plan (pr-4-3c-shadow-activation).md` (SYNTHESIS v2 — Claude + Opus
second-opinion; Codex quota-blocked until Jul 25). First half of the split 4.3c (4.3c-2 = graceful
supersede-of-active + safe-handover). **Dark/fail-closed: NO actuation/dispatch/Modbus; mode always
`shadow`.**

## What shipped
Activate a strict-TRUSTED, approved **v2** control plan into machine `CommandIntent`s written to a
durable append-only outbox, granting `machine_authority` (shadow) under a DB-level one-per-scope
mutex — all atomically.

- **`core/canonical_json.py`** — RFC-8785 JCS with ES6 number formatting; reproduces the 6.1a golden
  `capability_hash` + `canonical_json` BYTE-FOR-BYTE (the Python producer the golden was built for).
- **`core/device_capabilities.py`** — fail-closed loader (`load_device_capability_snapshot`): unset
  path ⇒ empty dark default (zero gates); unreadable/malformed/schema-violating/hash-mismatch ⇒
  throw. Independently RECOMPUTES + verifies the declared `capability_hash`. `capability_member`:
  EXACT membership (canonical-string compare, not float ==); non-member ⇒ `CapabilityMembershipError`.
- **`core/command_intent.py`** — one `CommandIntent` per gate event; **B2**: ids
  (uuid5 intent_id, idempotency_key) key on the GLOBAL `event_sequence`, not the per-gate
  `gate_event_sequence`. v2-only (`NonActivatablePlanError`); `Z`-suffixed UtcInstants; deterministic
  replay; `mode='shadow'`.
- **`core/activation_freeze.py`** — recomputable freeze (`machine_authority_granted=true` + capability
  + ordered intent-content hashes), v2 document wrapper (evidence in its own key), `verify_*`.
- **`core/control_plan_lifecycle.py`** — new `STATE_ACTIVATED='shadow_active'` + edges
  `shadow_activated`(approved→active) and emergency `invalidated`(active→invalidated). Non-terminal.
- **`migrations/0007`** — **B1**: relaxes the three 0003 `control_state_transitions` CHECKs
  (type/from_state/to_state/edge_graph) to admit shadow_active + the edges (down restores them, fails
  closed once a shadow_active row exists); `control_command_outbox` (append-only, 0001 immutability
  trigger, UNIQUE on global event_sequence + idempotency_key); `control_active_gate_authority`
  (MUTABLE one-per-scope mutex, PK (section_id,gate_id), NO immutability trigger).
- **ORM** (`models/control_plan.py`) — the two tables; drift lock + create_all-isolation extended
  (the mutex table is the documented immutability-trigger exemption).
- **repository** — atomic `insert_activation` (transition+outbox+mutex, ONE txn; deterministic
  scope-insert order; mutex PK conflict → `ScopeConflictError`, transition PK → `TransitionConflictError`)
  and **B3** `append_transition_and_release_scope` (invalidate-from-active releases the mutex atomically).
- **service** — `activate_control_plan` (state gate → trust gate `is_trusted_shadow_approval` → freeze
  re-verify → compile → build freeze/doc → atomic write); `invalidate_control_plan` releases the mutex
  when leaving shadow_active. Snapshot injected (empty dark default if unconfigured).
- **endpoint** — `POST …/activate` (`require_supervisor` + `require_strict_approval_policy`, builds
  authorization evidence); new errors mapped (activation conflicts → 409, config → 503).
- **schemas** — `ActivateRequest`; `shadow_active` added to `_LIFECYCLE_STATE`.
- **main.py / config** — snapshot loaded ONCE at startup (fail-fast) into `app.state`.

## Six dark-by-default gates (why it's safe to land behind the external cutover)
trust (`is_trusted_shadow_approval` — compat approvals untrusted) · route policy
(`require_strict_approval_policy` 503 in compat) · capability (empty snapshot ⇒ non-member) ·
quantizer membership (continuous position ⇒ non-member until 6.1b) · provenance (v1 ⇒ not activatable)
· `mode='shadow'` + no dispatcher.

## Gate
scheduler unit **631 passed / 20 skipped** (baseline 625 → +6 activation service tests; +41 new
core-module/edge tests earlier), 3× stable; pyflakes clean; ORM↔DDL drift + create_all isolation green.
Integration **20 passed on a real loopback Postgres** (existing 19 + the new 0007 migration test:
apply/rollback/reapply, B1 CHECK relaxation admits shadow_active + rejects an illegal edge, mutex
one-per-scope conflict + mutable DELETE, down refuses once a shadow_active row exists). Wiring: every
new core module has non-test importers (canonical_json→device/command/activation/service;
device_capabilities→main/service/endpoint; command_intent→activation/service/endpoint;
activation_freeze→service).

## 2-tier QCHECK: `/code-review high` (workflow, 15 agents) + Opus adversarial (Codex quota-blocked)
NO CRITICAL/HIGH. The two tiers produced DISJOINT findings (uncorrelated blind spots) and even
DISAGREED on one — resolved empirically. All fixed + re-verified (unit 634 ×3, integration 21 on real
Postgres, pyflakes clean):
- **[tier-1 CONFIRMED, tier-2 got it WRONG] repository.py — dead ScopeConflictError branch.** The
  branch keyed on `error.orig.constraint_name`, which SQLAlchemy's asyncpg adapter does NOT populate
  (it's on the wrapper's `__cause__`), so a real scope conflict was misclassified as
  TransitionConflictError. Tier-2 claimed it verified the opposite; a NEW real-repository integration
  test (tier-2's own MED coverage ask) settled it: the fake had masked it ([[test-fakes-pin-real-interface]]).
  Fixed with `_violated_constraint(error)` checking `orig` AND `orig.__cause__`; the real-PG test now
  asserts ScopeConflictError.
- **[tier-1 CONFIRMED] device_capabilities.py — non-UTF-8 file** raised UnicodeDecodeError (a
  ValueError, not OSError), escaping the fail-closed wrap → now `except (OSError, UnicodeDecodeError)`
  (+ test).
- **[tier-1 CONFIRMED] main.py — a broken capability config crashed the whole service** (health/draft/
  list). Now logged + degraded to the empty dark default (activation-only fail-closed), not a crash.
- **[tier-1 PLAUSIBLE] endpoint — `get_lifecycle_service` app.state coupling** → defensive `getattr`.
- **[tier-2 MED] no real-repo test for insert_activation/release** → added (and it caught tier-1 #1).
- **[tier-2 LOW] leaked pydantic ValidationError → 500** → caught in `compile_command_intents` as
  NonActivatablePlanError (409) (+ test).
- **[tier-2 LOW] NULL gate_id → NOT-NULL 500** → `_build_scope_rows` guard → ActivationNotAllowedError
  (+ test).
- **[tier-1 cleanup] stale "all four tables immutable" docstring** → corrected for the mutable mutex.
- **Skipped (LOW cleanups, documented):** invalidate's explicit branch (the two paths genuinely
  differ), the per-intent triple hash recompute (correctness-neutral), and `verify_activation_freeze`
  being production-dead (it's a tested build+verify counterpart 4.3c-2's supersede-of-active uses).

Both tiers confirmed the safety core: dark-by-default (trust + route gates), fail-closed compilation,
B1/B2/B3, atomic activation, JCS byte-parity with the 6.1a golden, and NO actuation/dispatch path.
