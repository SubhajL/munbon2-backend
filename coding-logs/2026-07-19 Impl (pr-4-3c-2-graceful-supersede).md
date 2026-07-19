# PR 4.3c-2 — graceful supersede-of-active + safe-handover (impl log)

**Date:** 2026-07-19 · **Base:** main `d1839481` (post-4.3c-1) · **Service:** `services/scheduler` (Python)
FINISHES PR 4.3c (4.3c-1 = activation core, #89). **Dark: only writes a lifecycle transition + deletes
a mutex row — NO actuation/dispatch.**

## What shipped
Retire an ACTIVE (shadow_active) incumbent — one that holds machine authority — by superseding it with
an approved successor, gated by a modeled-safe handover of EVERY gate, releasing the one-per-scope
mutex atomically.

- **`core/control_plan_lifecycle.py`** — new edge `("superseded", STATE_ACTIVATED, STATE_SUPERSEDED)`
  in `_EDGES` + `TRANSITION_TARGET`.
- **`migrations/0008`** — relaxes ONLY the 0007 `control_state_transitions_edge_graph` CHECK to admit
  that edge (from_state/to_state already admit shadow_active/superseded from 0007/0003). Down restores
  the 0007 form and fails closed once a `(superseded, shadow_active, superseded)` row exists.
- **`control_plan_projection_repository.py`** — renamed the private `_handover_verdicts` → public
  `gate_handover_verdicts` (shared, so supersede REUSES the exact per-gate construction, never forks
  it — its existing ledger-route caller updated).
- **`control_plan_lifecycle_service.py`** — `supersede_control_plan` now branches: after ALL the
  existing successor guards (approved + trusted + freeze-verified + same physical scope + same campaign
  + strictly-forward version), if the TARGET's derived state is `shadow_active` it runs
  `_require_safe_handover` (every gate must be `evaluate_safe_handover` `is_safe`, else
  `HandoverUnsafeError`) and appends the `superseded` transition + releases the mutex atomically via
  `append_transition_and_release_scope`; an approved (never-activated) target still takes the plain
  `_append` path (no mutex).
- **endpoint** — `HandoverUnsafeError` → 409.

## Rolling-campaign limitation (deliberate, tested)
`evaluate_safe_handover` requires a terminal `close`; a plan holding a gate OPEN across the horizon is
never modeled-safe to hand over, so a graceful supersede is refused (409). Such a plan is retired by
emergency `invalidate` (still available from `shadow_active`). Documented + tested
(`test_require_safe_handover_blocks_a_rolling_plan_without_a_terminal_close`).

## Gate
scheduler unit **637 passed / 22 skipped** (baseline 635 → +2 supersede-of-active safe + unsafe; +1
lifecycle edge test earlier), 3× stable; pyflakes clean. Integration **22 passed on real loopback
Postgres** (+the 0008 migration test: apply-all admits the edge, an undeclared edge rejected, down
refuses once a graceful-supersede row exists). Wiring: `gate_handover_verdicts` (service + ledger
route), `_require_safe_handover` (supersede), `HandoverUnsafeError` (endpoint) — all non-test.

## 2-tier QCHECK: `/code-review high` (workflow, 11 agents) + Opus adversarial (Codex quota-blocked)
NO CRITICAL/HIGH. Both tiers independently verified the safety core HOLDS (fail-closed handover of
EVERY authority-holding gate — the mutex-scope source `_physical_scope` and the checked-gate source
`gate_handover_verdicts` BOTH filter `planning_disposition=="scheduled"`, so none can escape; atomic
mutex release; all existing supersede guards preserved; successor activatable on the freed scope; no
actuation path; the rename broke no caller). All (cleanup-tier) findings fixed:
- **[tier-1 PLAUSIBLE latent hazard + tier-2 L1] mutex-release duplication → CENTRALIZED.** The
  release-on-leaving-shadow_active logic was copy-pasted in invalidate + supersede; a future terminal
  edge via the plain `_append` would have orphaned the mutex. Fixed by teaching `_append` to release
  the scope on ANY exit from `shadow_active` — both special-case blocks deleted; invalidate + supersede
  now just call `_append` (also removes the tier-1 #4 double-derive on the invalidate path).
- **[tier-1 CONFIRMED false-assurance] the rolling-plan test passed `ledger_entries=[]`,** so it was
  unsafe via `no_ledger_rows` regardless of the missing close (a test that couldn't fail for its named
  defect). Rewritten to ISOLATE the terminal-close: a SATISFIED + drained ledger row, safe WITH a close
  and unsafe WITHOUT — so only the close flips it.
- **[tier-1 CONFIRMED + tier-2 L3] test gaps** → added (a) an e2e unsafe-supersede through the REAL
  service path (monkeypatched verdict) asserting HandoverUnsafeError + the incumbent stays active/holds
  scope (no silent handoff), and (b) the successor activates on the freed scope after a graceful
  supersede.
- **[tier-2 L2] ProjectionCorruptError → 503.** A corrupt stored projection reaching the handover
  builder during supersede now fails closed with a 503 (like the ledger route), not an opaque 500.
- **Skipped (documented):** relocating `gate_handover_verdicts` to `core/` (tier-2 L1 — reuse-not-fork
  is correct; the move would churn `_parse_projection_json`); the residual supersede double-derive
  (tier-1 #4 — correctness-neutral, negligible on a tiny transition list). Tier-1 REFUTED one candidate
  (a claimed "narrowed integrity invariant" on the reused builder).

Post-fix: unit 638 ×3, integration 22 on real Postgres, pyflakes clean.
