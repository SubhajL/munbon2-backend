# Topology Reconciliation — star vs. serial-chain (F-11 follow-up)

**Date:** 2026-07-08 · **Trigger:** P1 item **B5** (conveyance loss) surfaced that the
canonical network topology adopted in **F-11** disagrees with the surveyed canal geometry.
**Status:** investigation only (no code changed). **Verdict:** the F-11 canonical topology
is **structurally wrong for the lateral canals**; correct it before B5, and re-verify A1–A3.

---

## 1. Executive summary

- The canonical `src/config/network.json` (adopted from `munbon_network_updated.json` in
  F-11) models every lateral canal as a **star** — all offtakes hang directly off the
  lateral head (e.g. `M(0,1) → {M(0,1;1,0..1,4)}`).
- The surveyed geometry (`canal_sections_6zones_final.json`, and the authoritative
  **SCADA "Section Detailed Information" V1.0** Excel it derives from) shows these are
  **serial chains** — water flows through each gate in sequence down the canal
  (`M(0,1;1,0) → 1,1 → 1,2 → 1,3 → 1,4`), with monotonically increasing chainage.
- This is not a naming/formatting artifact: **all 47 geometry nodes exist in the canonical
  network**; only the *edge wiring* differs, on **24 of 37 reaches**, across **zones
  1, 3, 4, 5, 6** (every zone except 2).
- The star is hydraulically impossible: you cannot feed the gate at km 6.8 directly from the
  lateral head at km 0 without passing through the intervening reaches. **The chain is
  physical reality.**
- **Impact:** B5 seepage can't be computed on reaches that don't exist as edges; and the
  already-merged **A1–A3** aggregation (#19) computes correct code over a wrong graph —
  lateral gate-flow *targets* are wrong (main-stem totals still conserve, so tests pass).

**Recommendation:** regenerate the canonical topology as serial chains — **deterministically
from the node names themselves** (the `M(i,j;…)` grammar encodes the full path; verified to
reproduce the survey 37/37 and yield a 60/60 spanning tree, §6.5) — as an "F-11b" correction,
re-verify A1–A3 on it, then do B5. No Excel extractor needed for topology. See §7.

---

## 2. The star-vs-chain evidence

Example — the M(0,1) lateral (zone 6):

| Reach (geometry, serial) | from_km → to_km | length | Canonical parent of the *to* node |
|---|---|---|---|
| M(0,1;1,0) → M(0,1;1,1) | 0+000 → 2+600 | 2600 m | M(0,1) *(star)* |
| M(0,1;1,1) → M(0,1;1,2) | 2+600 → 4+520 | 1920 m | M(0,1) *(star)* |
| M(0,1;1,2) → M(0,1;1,3) | 4+520 → 5+500 | 980 m | M(0,1) *(star)* |
| M(0,1;1,3) → M(0,1;1,4) | 5+500 → 6+780 | 1280 m | M(0,1) *(star)* |

- **Geometry:** each gate has exactly **one child** (the next gate down the canal); chainage
  increases monotonically; the node name `M(0,1;1,k)` = *k-th gate on sub-canal 1*.
- **Canonical:** `M(0,1)` has **5 direct children**, `M(0,12)` has **7**, `M(0,3)` has 5 —
  a manifold/star, which the geometry and the km chainage both contradict.

**Re-parented reaches by zone:** zone 1: 1, zone 3: 5, zone 4: 5, zone 5: 5, zone 6: 8
— **24 total** (systematic, not localized).

---

## 3. Topology file inventory (normalized ids, root = S)

| File | edges | nodes | reachable from S | geometry match | shape |
|---|---|---|---|---|---|
| `src/config/network.json` **(canonical)** | 59 | 60 | **60/60 ✓** | 13/37 | **STAR** |
| `src/munbon_network_updated.json` | 59 | 60 | 60/60 ✓ | 13/37 | STAR (= canonical) |
| `src/munbon_network_complete.json` | 58 | 60 | 3/60 ✗ | 13/37 | STAR (broken conn.) |
| `src/munbon_network_final.json` | 42 | 57 | 2/57 ✗ | **36/37** | **CHAIN** (broken conn.) |
| `src/network_structure_updated.json` | 69 | 59 | 3/59 ✗ | **36/37** | **CHAIN** (broken conn.) |
| `src/munbon_network_structure.json` | 30 | 42 | 2/42 ✗ | 24/37 | partial chain |

**Two families:** exactly one file is *connected* (the star canonical); the two files that
match the surveyed chain geometry (`final`, `network_structure_updated`) are stored as a
**disconnected forest**.

---

## 4. Root cause — why F-11 rejected the chain

The chain files (`final.json` etc.) omit the **junction edges** that connect each sub-lateral
head to its feeder. Built from geometry, the chain has **10 parent-less "root" nodes** and
reaches only 15/47 from M(0,0) — a *forest of per-canal chains*, not a tree.

That is the "**76 % wrong / 2 of 59 reachable**" finding F-11 recorded — but it is a
**connectivity defect, not wrong reaches**. F-11 "fixed" connectivity by adopting
`munbon_network_updated.json`, which re-wired every lateral into a **star** hanging off its
head. That restored reachability but **replaced the physically-correct serial reaches with
fictitious head→offtake reaches** on 24 of 37 reaches.

> Net: F-11 traded a *fixable* connectivity bug for a *structural* hydraulic error.

The correct topology = **geometry's serial chain reaches** + the **junction edges** (lateral
head → first gate of each sub-lateral) that stitch the forest into one tree rooted at S. The
canonical star already has the junction edges; it just needs the intra-lateral stars replaced
by chains.

---

## 5. Coverage — the 12 gates missing from the 37-section JSON

`canal_sections_6zones_final.json` has 37 of an intended 46 sections; **12 canonical gates
have no reach** in it (mostly deep zone-4/5/6 sub-laterals + the Waste Way):

`M(0,0;1,0)`, `M(0,12;1,1;1,0;1,0..1,2)`, `M(0,12;1,2;1,0;1,0..1,1)`, `M(0,12;1,3;1,0..1,1)`,
`M(0,12;1,4;1,0..1,1)`, `M(0,1;1,0;1,0)`, `M(0,1;1,1;1,2;1,0)`
(six of these carry real command area: 1121, 1555, 686, 1185, 1434, 337 rai).

**The SCADA V1.0 Excel closes this gap** (see §6).

---

## 6. Source-of-truth determination

**`SCADA Section Detailed Information 2025-08-23 V1.0 SL.xlsx` is authoritative** (newest;
the 37-section JSON derives from the older V0.95):

| Sheet | Content | Use |
|---|---|---|
| `Sheet1` (71 rows) | No. · Canal Name · Section · **Km→Km** · **Gate Valve (M-id)** · x,y · i,j,k | **59/59 canonical gates**, km ranges → reach lengths + serial order |
| `Characteristics` (117 rows) | คลอง · กม เริ่ม/สิ้นสุด · **ระยะ (length m)** · Qr · **Qmax** · Qd · **A (area m²)** · V · R | per-reach hydraulic geometry |
| `สบ. 1` (87 rows) | canal · structure · km · **FSL** · **sill level** · size · flow | gate sill/levels — also feeds F-01 real levels |

`Sheet1` gate-id column resolves to **59 distinct M-ids = 100 % of the canonical gates**, and
includes **all 12** gates the JSON was missing. Both the corrected **topology** (serial order
by canal + km) and full **per-reach geometry** are regenerable from this one workbook.

> Still absent everywhere: an explicit `seepage_rate_m_s` (a calibration parameter). B5's
> lining-default table (concrete/earth/unknown) remains the provisional source, per spec.

---

## 6.5 The topology is encoded in the node names (decisive)

The `M(i,j; …; a,p)` id **is** the path from the source to that valve. Each `;`-separated
pair `(branch, position)` names a canal and the valve's position along it, so the parent is a
pure string rule:

- **`p > 0`** → serial predecessor on the same canal: `(…, a, p-1)`.
- **`p == 0`** → first valve on a branch → **drop the last tuple** (junction to the valve on
  the parent canal where the branch takes off).
- single tuple `(0,0)` → root **S**.

Applying this rule to the **59 canonical gate names** (verified, `scratchpad/naming_topology.py`):

| Check | Result |
|---|---|
| every derived parent exists | **59/59** (0 dangling) |
| reachable from S | **60/60 — spanning tree ✓** |
| reproduces the surveyed geometry chain | **37/37 (100 %)** |
| edges matching the canonical star | 30/59 → **29 canonical edges are wrong** |

Two independent sources — the **naming grammar** and the **SCADA survey** — agree completely.
The Excel corroborates a third time: `Sheet1` carries explicit `i, j, k, l, m` columns (the
parsed tuples) next to each `Gate Valve`.

**Consequence:** the corrected topology needs **no Excel extractor and no km heuristics** — it
is a deterministic function of the node names already in `network.json`. The Excel/km is needed
only for reach **geometry** (length, cross-section) to feed B5/F-05.

---

## 7. Impact & recommended sequence

### Impact
- **F-11:** the adopted canonical topology is structurally wrong for laterals (24 reaches).
- **A1–A3 (#19, merged):** the aggregation *code* is correct and topology-agnostic, but on the
  star graph each lateral offtake's demand routes straight to the head, so the **intra-lateral
  reach flows — i.e. the per-gate control targets — are wrong**. Conservation at the head still
  holds, so the current tests (synthetic trees + main-stem conservation) stay green. This is a
  *silent* correctness gap for lateral gate control, not a crash.
- **B5:** blocked — seepage on the real serial reaches (2600 m, 1920 m, …) cannot be applied to
  edges that don't exist.

### Recommended sequence
1. **F-11b — corrected topology, derived from the node names** (§6.5). Add a pure
   `edges_from_names(gate_ids)` (parse → parent rule → edges) and regenerate
   `src/config/network.json`; assert `is_spanning_tree` + 60/60 reachable + that it reproduces
   the geometry survey 37/37. Deterministic, stdlib, no Excel/km needed for topology. TDD, one PR.
2. **Re-verify A1–A3** on the corrected graph — add a real-network assertion that a lateral's
   head reach carries the sum of the whole serial chain below it (catches star regressions).
3. **B5** — conveyance loss on the now-real serial reaches (the model from the approved B5 plan
   is unchanged; only the geometry it consumes becomes correct). Reach **geometry** (length via
   km ranges, cross-section) comes from the SCADA Excel `Characteristics` sheet at that point.

### Open choices for you
- Topology source is settled: **derive from the node names** (pure, complete 59/59, reproduces
  the survey 37/37) — no Excel extractor or `final.json` repair required.
- Whether to extract the `Characteristics`/`สบ.1` sheets (geometry + sill levels) in the B5 PR
  to unblock seepage and improve F-01, or keep F-11b to topology only (recommended: topology
  only in F-11b; geometry in B5).

---

## 8. Appendix — reproduction

Analysis script: `scratchpad/topo_analysis.py`. Key commands compared normalized edge sets of
all `munbon_network_*.json` against the geometry chain, checked reachability from S, and mapped
each geometry reach's downstream node to its canonical parent. SCADA Excel parsed with pandas
(`Sheet1` gate column, `Characteristics`/`สบ.1` headers).
