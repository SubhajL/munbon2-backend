# Munbon Remediation — PR Review Guide (P0 + P1)

**For:** senior team-lead review. **Repo:** `github.com/SubhajL/munbon2-backend`.
**`main` HEAD at writing:** `4e45795`. **Scope of this doc:** every remediation PR (#6–#24),
grouped P0 (audit fixes) and P1 (control-plane build-out), each with *what to scrutinize*.

## How to review
- All PRs below are **squash-merged**; open each with `gh pr view <n>` / `gh pr diff <n>`.
- The remediation design lives in `services/flow-monitoring/docs/remediation/`
  (`REMEDIATION_MASTER.md`, `GATE_CONTROL_REMEDIATION_SPEC.md`, `HYDRAULIC_REMEDIATION_SPEC.md`,
  `TOPOLOGY_RECONCILIATION.md`, `SEEPAGE_CALIBRATION.md`, `HANDOFF.md`).
- Flow-monitoring core logic is **pure/stdlib in `src/core/`**; tests run isolated:
  `pytest  # bare, from the service root (Wave 1.9); add a path for a single suite

## Status snapshot
- **P0: all 7 items merged** (#7–#13) + 4 QCHECK follow-ups (#15–#18) + a docs refresh (#14).
- **P1: 6 PRs merged** (#19–#24): aggregation → topology correction → conveyance loss →
  seepage calibration → service wiring → hardening.
- **3 PRs still OPEN and unreviewed** (#1–#3, sensor-data) — likely superseded; need a decision.
- **The whole P1 control engine is reachable via one endpoint** (`POST /api/v1/control/plan`);
  scheduler/SCADA-bridge/branch-split/demand-producer are **not built yet** (see "Not done").

---

## Summary table

| PR | Type | Item | One-line | Reviewer priority |
|----|------|------|----------|-------------------|
| #6 | docs | — | Accurate hierarchical CLAUDE.md for the polyglot monorepo | low |
| #7 | P0 | F-01 | Correct gate-flow law; kill the 287 m³/s blow-up | **high** (physics) |
| #8 | P0 | F-11 | Canonical network topology + connectivity guard | **high** (superseded by #20) |
| #9 | P0 | F-04 | Real per-reach canal capacity (was hardcoded 15.0) | med |
| #10 | P0 | C10 | Delete orphan duplicate flow-law impls + guard | med |
| #11 | P0 | F-08 | Restore missing JobScheduler so rid-ms boots | low |
| #12 | P0 | SEC | Move hardcoded DB creds → env + secret-scan CI gate | **high** (security) |
| #13 | P0 | F-07 | Tracked loader + schema for `gis.crop_registry` | med |
| #14 | docs | — | HANDOFF refresh (all P0 merged) | low |
| #15 | P0-fix | SEC | 8 more leaking `.py` + fix self-blocking scan gate | **high** (security) |
| #16 | P0-fix | F-07 | Missing `"Zone"` column + idempotent loader | med |
| #17 | P0-fix | C10/F-11 | Harden C10 guard regex + F-11 robustness | low |
| #18 | P0-fix | F-08 | Pin cron jobs to Asia/Bangkok | low |
| #19 | P1 | A1–A3 | Graph-descendants demand aggregation | **high** |
| #20 | P1 | F-11b | Correct star→serial-chain topology from node names | **CRITICAL** (re-wired a P0) |
| #21 | P1 | B5 | Conveyance (seepage+operational) loss | med |
| #22 | P1 | B5-cal | Recalibrate seepage to aged-concrete field values | **high** (provisional numbers) |
| #23 | P1 | F-03/C9 | Wire engine into FastAPI (`/control/plan`); kill 25.0 stub | **high** |
| #24 | P1-fix | — | Harden C9 + engine per Codex review | **high** |

---

## P0 — audit fixes (prior sessions; verify against the audit in HANDOFF.md §2)

### #7 — F-01 gate-flow law (**review the physics**)
- **Finding:** the wired law returned **287 m³/s at 10 % open** for an 11 m³/s gate — three stacked
  bugs (inverted `opening^K2`; `Hs` treated as absolute MSL; no `Cs` clamp) + hardcoded levels.
- **Change:** new `core/gate_flow.py` — corrected rating `Cs = K1·(Hs/Go)^K2` (Go in denominator),
  clamp [0.3,1.0], `q ≤ q_max` ceiling, **bisection** inverse. Repointed `hydraulic_service`. 28 tests.
- **Reviewer focus:** confirm the K1/K2 convention + the monotonicity/`≤1.2·q_max` regression tests;
  confirm real upstream/downstream levels are fed (F-01 still uses a *documented, logged fallback*
  where sensors/solver levels are absent — **P1 to supply real levels**).

### #8 — F-11 canonical topology + guard (**note: superseded by #20**)
- **Finding:** the wired `munbon_network_final.json` was ~76 % wrong (2/59 nodes reachable).
- **Change:** `core/network_topology.py` connectivity guard + canonical `src/config/network.json`
  (adopted `munbon_network_updated.json`). 12 tests.
- **Reviewer focus:** **this adoption was itself wrong and was corrected in #20** — the adopted
  topology "starred" the laterals. Review #8 and #20 together; #8's *guard* is still valid, its
  *chosen topology* is not.

### #9 — F-04 per-reach capacity
- **Finding:** `_get_canal_capacity` returned a hardcoded 15.0 m³/s.
- **Change:** `core/canal_capacity.py` — real `q_max` per reach (NaN-safe). 9 tests.
- **Reviewer focus:** capacity is currently *not yet enforced* at aggregation (B7 is P2).

### #10 — C10 delete duplicate flow laws
- **Change:** removed 5 orphan duplicate implementations + an anti-regression grep-guard test. 3 tests.
- **Reviewer focus:** confirm the guard actually fails if a new duplicate law is added; several
  divergent `calibrated_flow_model*` / `water_gate_controller_*` files still exist (non-P0 debt).

### #11 — F-08 restore rid-ms JobScheduler
- **Finding:** `rid-ms` imported a missing `jobs/job-scheduler` → wouldn't boot.
- **Change:** restored the module + a jest smoke test. **Reviewer focus:** is the restored logic the
  intended one, or a stub to boot?

### #12 + #15 — SEC credentials (**security-critical; review together**)
- **#12:** moved tracked service creds → env + `.github/workflows/secret-scan.yml` diff gate + `.env.example`.
- **#15:** the original SEC **missed 8 more leaking `.py`** (repo-root + `csv_exports/`) **and the
  scan gate self-blocked** (its own regex contained the password). Both fixed.
- **Reviewer focus (IMPORTANT):** the leaked password `__ROTATED_DB_PASSWORD__` **is still in git history and
  ~137 tracked files** — code changes cannot fix that. **A credential rotation + `git filter-repo`
  history purge is still outstanding** (external action). Verify the scan gate can't be bypassed.

### #13 + #16 — F-07 crop_registry
- **#13:** `bff-water-planning` schema migration `009` + env CSV loader (fail-closed).
- **#16:** the migration **omitted the `"Zone"` column the reader selects** (reader still crashed) and
  the loader was **non-idempotent** (dupes → double-counted demand). Fixed + ON CONFLICT.
- **Reviewer focus:** crop_registry population needs an upstream **GIS shapefile export** (external);
  recommend retiring it for `gis.agricultural_plots` (tracked as F-06, not done).

### #17/#18 — QCHECK follow-ups
- **#17:** C10 guard regex now catches `opening_m ** k2`; F-11 multi-parent test fix; `load_edges`
  raises `NetworkTopologyError`. **#18:** rid-ms cron pinned to `Asia/Bangkok` (was firing ~7h off at UTC).

> **P0 process note for the lead:** PRs #7–#14 were **self-merged without the QCHECK gate** (a process
> lapse); #15–#18 are the retroactive QCHECK fixes. Worth confirming the P0 items are now clean.

---

## P1 — control-plane build-out (this work; reviewed in most detail)

### #19 — A1–A3 graph-descendants demand aggregation (**high**)
- **Finding:** demand→gate aggregation used a hardcoded 3-zone path table + synthetic node IDs +
  per-zone granularity.
- **Change:** new pure `core/demand_aggregation.py` — `required_flow_per_reach(edges, node_demand)`:
  reach `(u,v)` carries the demand of the subtree rooted at `v` (leaves→root sweep). New thin
  `core/network_flow_controller.py`. `network_topology.py` gained `children_of` + `topological_order`.
  Stdlib only (spec's `networkx` pseudocode deliberately not used). 37 tests.
- **Reviewer focus:** (1) reach keys are `(u,v)` tuples — the `C_{u}_{v}` bridge to `canal_capacity`
  is deferred. (2) `reach_loss` seam added for B5. (3) The engine had **no runtime caller** until #23
  (intentional offline-first phasing). (4) Aggregation correctness depends on the graph being a
  **spanning tree** — which #8's topology satisfied but with the *wrong* parent links (see #20).

### #20 — F-11b serial-chain topology (**CRITICAL — this re-wired a merged P0**)
- **Finding (surfaced while planning B5):** the F-11 canonical topology **stars** lateral canals
  (all offtakes hang off the lateral head) but the surveyed geometry + the `M(i,j;…)` node-id grammar
  show they are **serial chains**. **29 of 59 edges were wrong.** Full evidence in
  `TOPOLOGY_RECONCILIATION.md`.
- **Change:** pure `network_topology.edges_from_names(gate_ids)` derives the parent of each node from
  its name (`p>0` → serial `(a,p-1)`; `p==0` → drop last tuple; `M(0,0)` → root S). Regenerated
  `src/config/network.json` edges from the grammar; `gates`/node-set unchanged. A test **locks** the
  committed file to `edges_from_names(gates)`, and an independent **SCADA survey oracle** confirms 37/37.
- **Reviewer focus (IMPORTANT):**
  - This **changes the output of a merged P0 (F-11)** and the graph #19 aggregates over. The
    aggregation *code* is topology-agnostic; only the data changed. **Confirm you agree the
    serial-chain interpretation is physically correct** (chainage is monotonic down each canal; the
    node-name grammar encodes the path).
  - The naming-grammar parent rule assumes **contiguous positions** and a **single head `M(0,0)`** —
    #24 later added negative-index rejection; confirm no other malformed-id path.
  - Only **13/59** reaches matched before the fix vs **37/37** of the survey after — big structural change.

### #21 — B5 conveyance loss
- **Change:** new pure `core/conveyance_loss.py` — `seepage = rate·wetted_perimeter(cs,0.7·depth)·length`,
  `uplift = seepage + op_frac·throughflow`; `make_reach_loss` fills the #19 seam. New service-local
  `src/config/canal_geometry.json` (37 surveyed sections). Controller gained `geometry_path` +
  `apply_losses` flag + `reaches_missing_geometry`. Single pass is exact (fixed-depth seepage).
- **Reviewer focus:** **37/59 reaches have geometry; 22 are flagged missing → 0 loss (never fabricated).**
  Geometry for the 22 deep sub-laterals is a later SCADA-`Characteristics` extraction. Loss is opt-in;
  `apply_losses=False` is byte-identical to A1–A3.

### #22 — B5 seepage calibration (**high — the numbers are provisional**)
- **Finding:** #21 shipped **new-concrete** seepage (`3e-7`) + a **per-reach 5 %** operational loss,
  which compounds with gate-node count (a discretization artifact) → an implausible ~+55–90 % loss.
- **Change:** recalibrated to **aged-concrete field values** (`concrete 1e-5`, `earth 2e-5`,
  `unknown 1.5e-5`) and **`operational_loss_frac 0.05 → 0`** (seepage is the dominant, per-length,
  discretization-invariant loss). Full sourcing in `SEEPAGE_CALIBRATION.md`; a plausibility test
  bounds the LMC to 20–120 L/s/km. Now ~68 L/s/km (~22–28 % over the 36 km LMC).
- **Reviewer focus (IMPORTANT):** these are **literature values for comparable aged systems, NOT
  Munbon measurements** — explicitly PROVISIONAL pending a **Tier-3 inflow/outflow calibration**.
  Verification was done by direct FAO/Turkish-field-study fetch (the automated verify pass had
  rate-limited). A domain reviewer should sanity-check `1e-5 m/s` for Munbon's canals.

### #23 — F-03/C9 wire the engine into the service (**high**)
- **Change:** new `api/control.py` + `schemas/control.py` — **`POST /api/v1/control/plan`** (node-keyed
  demand → per-reach flow, optional B5 loss; fail-closed: 400/503). `main.py` lifespan constructs
  `NetworkFlowController` on the **canonical** config and sets `control_api.flow_controller`. **Retired
  the `25.0` stub** (`_get_system_demand` now fail-closed-raises). **Also fixed a `settings.py`
  `NameError` (`Optional` unimported) that made the whole service unimportable** — a prerequisite so
  the wiring actually boots. 8 DB-free tests.
- **Reviewer focus (IMPORTANT):**
  - **Scope = stateless `/plan`** (demand in the body). The fuller stored `/demands` contract (C12)
    needs demand persistence + the ros-gis producer + `section_node_map` (A4, blocked). So **there is
    no real demand producer yet** — `/plan` is driven by whatever the caller posts.
  - **The legacy `DualModeGateController` is still constructed on the wrong files**
    (`main.py:42` → `munbon_network_final.json` (the #20-rejected star) + the 4-section template). It
    drives the *old* hydraulic solver; flagged, not repointed. **Two topology sources coexist** — worth
    a decision.
  - A pre-existing service-boot bug (settings) was bundled in; arguably should have been its own PR.

### #24 — Harden C9 + engine per Codex review (**high — read alongside #23**)
- **Context:** the Codex adversarial second-opinion had been **skipped since #19**; when finally run it
  found real defects in the shipped C9. This PR fixes the confirmed ones (Codex re-reviewed the fixes:
  no new CRITICAL/HIGH).
- **Fixes:** **[HIGH]** non-finite demand (`1e400`→inf) reached the engine → **HTTP 500**; now rejected
  in the handler → clean 400 (not via pydantic `allow_inf_nan`, which 500s on its own error echo).
  **[MED]** `generate_manual_instructions` swallowed the retired-stub `RuntimeError` → the **live**
  `GET /gates/manual/instructions` returned empty instead of "unavailable" → now 503. **[MED]**
  `NetworkTopologyError`→503 (was mis-mapped to 400) + `is_spanning_tree` enforced at construction.
  **[MED]** geometry fails **closed** on empty file. **[MED]** `main.py` `global kafka_consumer`
  (pre-existing shutdown `UnboundLocalError` when Kafka disabled = default). **[LOW]** reject negative
  node indices / non-numeric demand.
- **Reviewer focus:** confirm the fail-closed matrix (400 for bad demand, 503 for server/topology,
  clean errors for NaN/Inf/non-numeric/non-tree/empty-geometry). **Process:** some P1 PRs (#20–#23)
  shipped **without the Codex adversary** — a reviewer may want to re-run it over #20/#21/#22 too.

---

## Cross-cutting concerns for the lead

**Not done yet (explicitly out of scope so far):**
- **B8** branch-split coordinated inverse (reach target flow → per-gate openings via the F-01 law).
- **B6/B7** rotation scheduler + capacity enforcement (P2). **F-02/§9** SCADA discrete-level bridge (P2).
- **C12** stored demand contract + **the real demand producer (ros-gis)**; **A4** `section_node_map`
  (blocked on an unwired ros-gis spatial layer). **F-06/F-09** demand-source reconciliation.
- **SV** Saint-Venant/Manning façades returned (until Wave 1.4 deleted them; those routes now answer 501) hardcoded literals.
- Repoint/retire the **legacy `DualModeGateController`** off the stale `munbon_network_final.json`.
- Geometry for the **22 uncovered reaches**; **Tier-3 seepage calibration**; expand gate calibration
  beyond 10/59.

**External actions code can't fix (must be scheduled):**
- 🔐 **Rotate `__ROTATED_DB_PASSWORD__` + purge git history** (`git filter-repo`) — still in ~137 files + history.
- **GIS shapefile export** for crop_registry; **real sensor/solver water levels** for F-01.

**Known debt / caveats a reviewer will hit:**
- Divergent duplicate impls remain (`calibrated_flow_model*`, `water_gate_controller_{…}`) entangled
  with viz scripts; rid-ms `src/` (compiled JS) vs `src_typescript_backup/`.
- DB-coupled test suites (`test_api_endpoints`, influx/timescale) can't run isolated; pre-existing
  failures in `test_gate_registry`/`test_calibrated_gate_hydraulics`/`test_enhanced_hydraulic_solver`/
  `test_gradual_transition_controller` are **unrelated** to this work.
- Repo has aggressive blanket `.gitignore`s (`docs/`, `tests/`, `scripts/`) with grandfathered tracked
  files; `docs/remediation/**` is whitelisted.
- **Process:** several P1 PRs were self-merged (the lifecycle here is open-PR → admin-merge). The Codex
  QCHECK gap on #20–#23 is the main process finding.

**Open PRs needing a decision (#1–#3):** three sensor-data / frontend water-level PRs predating this
work — likely superseded. Recommend review-and-close or rebase.
