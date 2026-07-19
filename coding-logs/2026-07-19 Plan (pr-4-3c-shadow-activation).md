# PR 4.3c — shadow activation + transactional outbox (+ supersede one-per-scope & safe-handover)

**Service:** `services/scheduler` (Python/FastAPI). **Base:** main `92516380` (post-6.1a).
**Roadmap:** roadmap doc line 321 — "shadow ACTIVATION and transactional outbox, consuming only
post-hardening approvals and exact [6.1a] capabilities" + the supersede one-per-scope/safe-handover
deferred from 4.3b. Final PR of the active /goal.

## Overview
Convert an `approved_for_shadow`, **strict-trusted** control plan into machine **command intents**
(the frozen 6.0 `command-intent` contract) written to a durable append-only **outbox**, moving the
plan to a new `shadow_active` state and granting `machine_authority` (mode `shadow` only — NOTHING
dispatches or actuates; 6.2 validates, 6.3 dispatches). Enforce **one active plan per physical
`(section_id, gate_id)` scope**, and extend supersede so retiring an *active* incumbent requires a
**safe-handover** certification. The whole activation path is **fail-closed dark**: it is
unreachable unless (a) the claim policy is `strict` AND the approval is `is_trusted_shadow_approval`
(→ blocked in today's compat default), (b) a device-capability snapshot is configured, and (c) every
gate event's target is an exact capability quantizer member — so it lands safely behind the external
trust cutover.

## Dark-by-default gates (why this is safe to land now)
1. **Trust gate** — activation requires the plan's `shadow_approved` document to pass
   `is_trusted_shadow_approval` (strict claim policy + supervisor/admin evidence). Today's default is
   `compat` → no approval is trusted → activation 409s. (Same gate `supersede` already uses.)
2. **Endpoint policy gate** — the activate route carries `Depends(require_strict_approval_policy)`
   (503 in compat), exactly like `approve-for-shadow`.
3. **Capability gate** — no configured snapshot ⇒ empty dark default (zero machine-capable gates) ⇒
   every gate is a non-member ⇒ activation fails closed.
4. **Quantizer-membership gate** — a continuous optimizer position that is not an exact capability
   target member fails closed (continuous→discrete quantization is 6.1b's job).
5. **Provenance gate** — only v2 (artifact-reference) plans carry the lineage a `CommandIntent`
   requires; a v1 plan cannot be activated.
6. **mode = `shadow`** on every intent; NO dispatcher/SCADA/Modbus call anywhere (6.2/6.3 own that).

## Files to change

### New — core (pure, I/O-free, unit-tested)
- **`src/core/canonical_json.py`** — a minimal RFC-8785 (JCS) canonicalizer + `sha256_jcs`. Numbers
  via ES6 `Number.prototype.toString` semantics (integer-valued floats collapse `2.0`→`2`; exponent
  form matches `1e-7`; `-0`→`0`). Conformance-tested against the 6.1a golden
  `contracts/machine-boundary/golden/device-capability-hash.golden.json`
  `number_canonicalization_vectors` + reproduces the golden `capability_hash` and `canonical_json`
  BYTE-FOR-BYTE (this is the Python producer/verifier the 6.1a golden was built for).
- **`src/core/device_capabilities.py`** — `load_device_capability_snapshot(env)`: fail-closed loader
  from `SCHEDULER_DEVICE_CAPABILITY_SNAPSHOT_PATH` (unset/blank ⇒ empty dark default, zero gates),
  validated against the embedded 6.0 schema via `jsonschema`; RECOMPUTES `capability_hash` with
  `canonical_json` and rejects a snapshot whose declared hash ≠ recomputed (tamper/​drift → throw).
  Mirrors 6.1a's TS loader semantics. `capability_member(snapshot, canonical_gate_id, position_m)`
  → `(device_id, adapter_gate_id, target_level, capability_release_id, capability_hash)` or raises
  `CapabilityMembershipError` (unknown gate / non-member position).
- **`src/core/command_intent.py`** — pure compiler `compile_command_intents(record, snapshot, *,
  activation_sequence, request_id, not_before_for, deadline_for)` → `list[CommandIntent]` (the
  `schemas.machine_boundary.CommandIntent` model). One intent per `gate_plan_event`. Deterministic
  content-addressed ids: `intent_id = uuid5(NS, f"{plan_id}:{plan_version}:{gate_event_sequence}")`,
  `correlation_id = uuid5(NS, f"{plan_id}:{plan_version}:activation:{activation_sequence}")`,
  `idempotency_key = f"cmd.{plan_id}.{plan_version}.{gate_event_sequence}"` (id_token). Builds
  `CommandLineage` from the v2 record; sets `mode="shadow"`; validates the close/open position
  invariant (already in the model). `command_intent_content_hash(intent)` = `sha256_jcs` over the
  intent dict (drives outbox `intent_content_hash` + 6.2's receipt).
- **`src/core/activation_freeze.py`** — `build_activation_freeze(record, *, snapshot,
  intents, requirement_set_sha256)` and `verify_activation_freeze(document_text, record, ...)`:
  the recomputable activation-lineage freeze, mirroring the 4.3b approval-freeze pattern.
  Freezes `machine_authority_granted=true`, `capability_release_id`, `capability_hash`,
  the ordered `intent_content_hash` list + a set hash, and the approval-transition sequence it
  activates. Evidence lives in a separate `authorization_evidence` key (same v2 wrapper split as
  approval).

### Modified — core
- **`src/core/control_plan_lifecycle.py`** — add `STATE_ACTIVATED = "shadow_active"`; add edges
  `("shadow_activated", STATE_APPROVED, STATE_ACTIVATED)`, `("superseded", STATE_ACTIVATED,
  STATE_SUPERSEDED)`, `("invalidated", STATE_ACTIVATED, STATE_INVALIDATED)` to `_EDGES` +
  `TRANSITION_TARGET`. `STATE_ACTIVATED` is NON-terminal. (Cancel is pre-activation only — an active
  plan is retired by supersede-with-handover or emergency invalidate.)

### Modified — service / endpoints / repository / schemas
- **`src/services/control_plan_lifecycle_service.py`** — `activate_control_plan(...)`:
  load → require derived state `approved_for_shadow` → load + trust-check the approval document
  (`is_trusted_shadow_approval`, else 409) → `verify_shadow_approval_freeze` still matches → require
  v2 provenance → **one-per-scope**: insert the scope mutex (see migration), a conflict → 409 → compile
  intents against the configured snapshot (membership failures → 409) → build activation freeze +
  document (with authorization evidence) → in ONE txn append the `shadow_activated` transition, insert
  the outbox rows, and insert the scope-mutex rows. Extend `supersede_control_plan` to accept a
  `shadow_active` target: when the target is active, run `evaluate_safe_handover` per gate and require
  every gate safe (else `SupersedeScopeError`), and DELETE the target's scope-mutex rows in the same
  txn (releasing the scope). The snapshot is injected (constructor dep) so tests pin it.
- **`src/api/v1/endpoints/control_plans.py`** — `POST /{plan_id}/versions/{plan_version}/activate`
  (`Depends(require_supervisor)`, `Depends(require_strict_approval_policy)`), builds
  `authorization_evidence` exactly like approve, delegates to `service.activate_control_plan`. Map the
  new errors (`CapabilityMembershipError`, `ScopeConflictError`, `HandoverUnsafeError`) → 409;
  `DeviceCapabilityConfigError` → 503.
- **`src/repositories/control_plan_repository.py`** — `insert_command_outbox(session, rows)`,
  `acquire_scope_mutex(session, plan_id, plan_version, scope_pairs, activation_sequence)` (INSERT ...
  the PK conflict surfaces as `ScopeConflictError`), `release_scope_mutex(session, plan_id,
  plan_version)`, and load helpers for tests. All within the caller's txn.
- **`src/schemas/control_plan.py`** — `ActivateRequest` (reason + `evidence_refs`, mirroring
  `ShadowApprovalRequest`); extend the response's `lifecycle_state` Literal set with `shadow_active`.
  (No new response fields; the outbox is not projected here — a bounded outbox read can be 6.2/6.3.)
- **`src/core/config.py`** — add `scheduler_device_capability_snapshot_path: Optional[str] = None`
  (unset ⇒ dark default).

### New — migration pair (0007)
- **`migrations/0007_control_plan_shadow_activation.up.sql` / `.down.sql`**:
  - `scheduler.control_command_outbox` (append-only, reuses the 0001 immutability trigger fn): columns
    mirror `CommandIntent` — `intent_id UUID PK`, `correlation_id UUID`, `request_id TEXT`,
    `idempotency_key TEXT UNIQUE`, `canonical_gate_id TEXT`, `event_kind TEXT CHECK IN
    ('open','trim','close')`, `event_sequence INT`, `gate_event_sequence INT`, `device_id TEXT`,
    `adapter_gate_id TEXT`, `capability_release_id TEXT`, `capability_hash TEXT`,
    `target_position_m DOUBLE PRECISION`, `target_level INT`, `not_before TIMESTAMPTZ`,
    `deadline TIMESTAMPTZ`, `mode TEXT CHECK (mode='shadow')`, `intent_document_text TEXT` (canonical
    JCS), `intent_content_hash TEXT`, `plan_id UUID`, `plan_version INT`,
    `activation_transition_sequence INT`, `created_at TIMESTAMPTZ`; FK `(plan_id,plan_version)` →
    `control_plan_runs`; UNIQUE `(plan_id, plan_version, gate_event_sequence)`.
  - `scheduler.control_active_gate_authority` (MUTABLE current-authority index — NO immutability
    trigger; the append-only transitions remain the audit authority): PK `(section_id, gate_id)`,
    columns `plan_id UUID`, `plan_version INT`, `activation_transition_sequence INT`,
    `granted_at TIMESTAMPTZ`; FK `(plan_id,plan_version)` → `control_plan_runs`. The PK is the DB-level
    **one-per-scope mutex** (INSERT conflict = scope occupied). Documented as derived current-state
    (5.2 makes it restart-safe/re-derivable).
  - down: DROP both (only while empty; else forward-fix), matching 0002/0003 down conventions.

## Test coverage (bare pytest = the gate; disposable loopback PG for migration/integration)
- `tests/unit/test_canonical_json.py` — golden number vectors each canonicalize exactly; reproduces
  the golden `canonical_json` + `capability_hash`; key-order independence; `-0`/`1e-7`/`2.0` cases.
- `tests/unit/test_device_capabilities.py` — empty dark default; valid load + hash recompute; declared
  hash ≠ recomputed → throws; unknown gate / non-member position → CapabilityMembershipError; exact
  member returns the device+level tuple.
- `tests/unit/test_command_intent.py` — one intent per event; deterministic ids (replay-stable);
  close→pos 0, open/trim→pos>0; v2 lineage exact; mode shadow; content hash independent oracle.
- `tests/unit/test_activation_freeze.py` — freeze recomputes from immutable rows; tamper → mismatch;
  machine_authority_granted true; evidence in its own key.
- `tests/unit/test_control_plan_lifecycle.py` (extend) — new edges legal/illegal; shadow_active
  non-terminal; activate illegal from draft/under_review/cancelled.
- `tests/unit/test_control_plan_lifecycle_service.py` (extend) — activate happy path (strict trusted,
  configured snapshot) writes N intents + mutex + transition; compat/untrusted → 409; non-v2 → 409;
  non-member position → 409; scope already active → 409; supersede active incumbent requires safe
  handover (unsafe → 409, safe → superseded + mutex released).
- `tests/integration/test_migration_0007.py` (env-gated) — apply/rollback/reapply; outbox
  immutability (UPDATE/DELETE blocked); scope-mutex PK conflict; ORM↔DDL drift lock extended.
- `tests/integration/test_activate_endpoint.py` (env-gated) — 401/403 (role), 503 in compat
  (require_strict_approval_policy), 409 non-activatable, happy path under strict.

## Wiring Verification
| Component | Entry point | Registration | Schema/Table |
|---|---|---|---|
| `activate_control_plan` | `POST …/activate` handler | endpoints/control_plans.py router (already mounted) | control_state_transitions, control_command_outbox, control_active_gate_authority |
| `compile_command_intents` | `activate_control_plan` | import | (pure) |
| `load_device_capability_snapshot` | lifecycle service ctor dep, wired in `get_lifecycle_service` | import + config path | reads the configured JSON file |
| `canonical_json`/`sha256_jcs` | device_capabilities + command_intent | import | (pure) |
| `control_command_outbox` | `insert_command_outbox` | migration 0007 | new table |
| `control_active_gate_authority` | `acquire/release_scope_mutex` | migration 0007 | new table |

## Cross-language / schema verification
- Command-intent shape: reuse `schemas.machine_boundary.CommandIntent` (already the drift-locked 6.0
  mirror; the 6.0 contract test binds it to `command-intent.schema.json`). No new contract.
- `capability_hash` JCS parity: `test_canonical_json.py` reproduces the 6.1a golden byte-for-byte —
  the TS producer (6.1a) and this Python verifier now share one oracle.
- Table/column names: `control_plan_runs(plan_id, plan_version)` FK verified against 0001;
  `(section_id, gate_id)` come from `control_plan_requirements` (scheduled disposition) per
  `_physical_scope`.

## Risks + rollback
- **Python JCS correctness** is the subtlest piece (ES6 number formatting). Mitigated by the golden
  conformance vectors as an independent oracle; if a number class can't be matched, fail closed
  (never emit a wrong hash). If JCS proves too costly, fallback: bind the snapshot's declared
  (schema-validated) hash and defer independent recompute to 6.2 — a documented, weaker option.
- **Mutable mutex table** vs append-only purity — deliberately separated as current-state; 5.2 owns
  restart-safe re-derivation. Alternative considered: advisory-lock + derived-state scan (no mutable
  table) — rejected as harder to test with equal safety.
- Everything is additive + dark; rollback = revert the PR (0007 down drops the two new tables while
  empty). No behavior change to existing routes.

## Time estimate
~1.5–2 focused sessions (large: state machine + intent compiler + JCS + outbox migration + mutex +
handover + endpoint + ~9 test files), full 2-tier QCHECK.

---

# SYNTHESIS v2 (after the second-opinion adversarial review — Plan agent/Opus, Codex quota-blocked)

The review confirmed the architecture (dark-by-default layering, mutex-as-materialized-index, reuse
`evaluate_safe_handover`, v2-only, exact membership) but found **3 P0 blockers** + refinements. All
adopted. Decisions:

**SPLIT the PR** (safety-motivated, consistent with the 4.4a/4.4b sub-PR pattern):
- **4.3c-1 = activation core** — `shadow_active` state + edges, `activate` endpoint, per-event
  `CommandIntent` compilation, `control_command_outbox`, the one-per-scope mutex, capability
  membership + JCS. One-per-scope enforced by REJECTION (409 if scope occupied). An active plan is
  retired only by emergency `invalidate` (releases the mutex). Lands first, full lifecycle + 2-tier
  QCHECK — tight blast radius on the authority-grant core.
- **4.3c-2 = graceful retirement** — extend `supersede` to accept a `shadow_active` target, gated by
  `evaluate_safe_handover` (reusing `control_plan_projection_repository._handover_verdicts:664`, NOT a
  fork), releasing the mutex atomically.

**P0 fixes folded into 4.3c-1:**
- **B1 (migration CHECKs):** 0007 MUST `DROP`+`ADD` the three `0003` `control_state_transitions`
  CHECKs (`_from_state`, `_to_state`, `_edge_graph`) to admit `shadow_active` + the new edges — else
  the append raises `23514`, which `append_state_transition` re-raises (not 23505) → 500. `.down`
  restores the 0003 forms and only succeeds while no `shadow_active` row exists (0003's pattern).
- **B2 (id collision):** `gate_event_sequence` is a PER-GATE counter (control_plan_service.py:711) →
  key `intent_id`/`idempotency_key`/outbox `UNIQUE` on the globally-unique **`event_sequence`**
  instead (the intent already carries it and it totally orders the plan).
- **B3 (mutex orphan):** release the mutex on EVERY `shadow_active` exit — 4.3c-1 covers
  `invalidate`-from-active structurally (release keyed on `from_state == STATE_ACTIVATED` in the
  append helper); 4.3c-2 adds the `supersede`-from-active exit.

**Other adopted refinements:**
- Deterministic scope-INSERT order (sort `(section_id,gate_id)`) + map Postgres `40P01` deadlock →
  409 (not 500).
- `UtcInstant` MUST end in `Z` — `datetime.isoformat()` yields `+00:00` and fails the regex; format
  via `astimezone(utc)`→ naive → `…Z`, cap fractional digits at 6; test `deadline >= not_before`.
- Explicit 409 for a non-v2 plan BEFORE compilation (never a leaked pydantic `ValidationError`→500);
  map `CapabilityMembershipError`/`ScopeConflictError` → 409, `DeviceCapabilityConfigError` → 503.
- Membership compares via the canonical number STRING (not float `==`); test the near-miss.
- ORM models for BOTH new tables on `ControlBase`; extend `test_control_models_match_migration_ddl`
  AND confirm `test_create_all_isolation` still holds (both migration-owned; the mutex table is
  mutable — NO immutability trigger — but still isolated from `Base.metadata.create_all`).
- A shared **"activatable plan" test builder** (feasible v2 + completed 3-member prediction + clean
  ledger + strict-trusted approval + a snapshot pinned to the plan's canonical gate ids + positions
  on exact targets) — the review flags this fixture as the biggest threat to landing; build it once,
  reuse across unit + integration.

**Kept over the review's dissent — the Python JCS stays in 4.3c-1** (recompute + verify the snapshot
`capability_hash`, fail-closed on any number outside the golden-tested range). Rationale: I PROVED a
~40-line `Decimal(repr).normalize()`+ES6 formatter reproduces the 6.1a golden BYTE-FOR-BYTE (all 7
vectors, `canonical_json`, and `capability_hash` `dc4f089d…`) — so the review's "it's subtle/risky"
argument is retired, and recomputing gives activation-time integrity (reject a tampered snapshot
before granting authority) that binding the declared hash cannot. It is the exact Python
producer/verifier the 6.1a golden was built for.

**Documented (not code) for the 6.2/6.3 contract:** a dispatcher MUST act only on outbox rows whose
plan is STILL `shadow_active` and still holds the mutex (never stale intents left by an
invalidate/supersede); the two-step supersede→activate control gap is benign in shadow but must
become atomic transfer once 6.3 dispatches; `evaluate_safe_handover`'s terminal-`close` requirement
may block a legitimately rolling multi-day campaign (test this in 4.3c-2); the gate-id namespace
(`gate_plan_events.gate_id` == snapshot `canonical_gate_id`) is assumed and fail-closed on mismatch —
confirm against the real capability snapshot at 6.1b/6.2.

**NEXT ACTION:** implement **4.3c-1** via g-coding TDD.
