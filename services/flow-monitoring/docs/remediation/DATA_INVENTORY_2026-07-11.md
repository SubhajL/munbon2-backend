# Munbon data inventory & forward-wave plan — rev. 3 (2026-07-12)

**Purpose.** A senior lead should be able to confirm every claim against (a) the codebase,
(b) the live AWS DB, and (c) the two source workbooks. Tags: `[DB]` live read-only SELECT
(2026-07-11/12); `[repo]` tracked file; `[xls:SCADA]` / `[xls:PLAN]` the two workbooks
below, both independently re-verified with openpyxl.

**Source workbooks (identity by SHA-256):**
- `SCADA Section Detailed Information 2025-08-23 V1.0 SL.xlsx` (repo root) —
  `b796361cb19a76074e10da9e0a4ed46eb50b26b556192c37738a4490a230be11`
- Annual plan `แผนการส่งน้ำประจำปี 2569-ฤดูฝน.xlsx` (operator's, not yet in repo) —
  `7821d7b8b6df0af1fd69da4da2d3a0a00198efc691d560ca536e052f32d118a5`

**Revision history.** rev. 1 (migration-inference) was too optimistic; rev. 2 corrected it
to "7 data gaps" after a live DB pass + Codex adversarial review; **rev. 3 adds the two
workbooks**, which materially unblock 2.1–2.5 and 2.4 — all findings below were
re-verified, not taken on faith. (Codex's review at `.codex/coding-logs/munbon2-backend-review.md`
was checked claim-by-claim; every checkable item confirmed.)

> ⚠️ **Security.** DB queries used the un-rotated leaked password (**E1**). Never commit
> the DB host/password literal — `secret-scan.yml` rejects newly-tracked carriers of the
> host. This file uses `<DB_HOST>`/`<DB_PASSWORD>` placeholders. (Workbook SHA-256 hashes
> are file identifiers, not secrets, and are safe to record.)

---

## 1. SCADA workbook — the canonical engineering source `[xls:SCADA]`

Sheets: `Sheet1`, `Characteristics`, `Experiment`, `สบ. 1`, `สบ. 2`.

### 1.1 Canonical network identity — COMPLETE (unblocks 2.1)
`Sheet1` "Gate Valve" column holds **59 gate ids** that, once whitespace-normalized,
**match the 59 gates in `network.json` exactly** (`set == set`, 0 symmetric difference)
`[xls:SCADA][repo]`. It also carries topology tuples (`i,j,k,l,m,n`), canal names,
chainages, zones, area (rai), and the geometry/calibration columns below. This
independently confirms `TOPOLOGY_RECONCILIATION.md` and is sufficient to begin **PR 2.1**.

### 1.2 Candidate section→gate crosswalk — NEARLY COMPLETE, MISLABELLED (reframes 2.5)
Of the 59 gate rows, **42 carry a numeric Section value** (17 internal gates blank).
Values run **1–41, 41 distinct, with duplicate 40 and no 42/43; sections 1 & 2 appear but
are not command-area sections** in the live suffix set (live command sections are 03–43,
= 41 sections) `[xls:SCADA][DB]`. Codex's proposed correction (drop head rows 1&2; shift
RMC/4L-RMC 40→41, 41→42; the blank FTO337 row → 43) yields each live suffix 03–43 exactly
once. **This must not be auto-loaded** — RID must confirm (a) the renumbering, (b) that
"Gate Valve" on a section row means the *supplying/control* gate, (c) whether section 40
legitimately spans two reaches. **PR 2.5 (section→gate half) becomes: validate → correct →
RID-approve → version → load a crosswalk**, no longer "wait for GIS to discover it." (The
*parcel→section* half still needs GIS — §3.)

### 1.3 Hydraulic geometry — rich enough to start 2.2 `[xls:SCADA]`
`Characteristics` has **99 hydraulic subsegments** (14 canal groups incl. LMC/RMC/9R-LMC/
38R-LMC + deep laterals), with Manning n / slope / bottom width / depth on ~98/99 and Qmax
on 62/99. **But:** Sheet1 has 18 canal-name values vs 14 Characteristics groups (Outlet,
Waste Way, FTO 2+450, FTO337 Rai absent as groups); 6 of the 22 currently-missing gate rows
lack a numeric Sheet1 length. **PR 2.2 needs a generated 59-edge coverage report** (edge →
canal → chainage → Characteristics rows) before claiming 100%.

### 1.4 ⚠️ The existing converter has a 1000× length bug (blocks naïve 2.1) `[repo][xls:SCADA]`
`services/flow-monitoring/scripts/excel_to_canal_sections.py` reads Sheet1 `ระยะทาง (เมตร)`
("distance in metres") and writes it to `length_m`. **But that column is mislabelled — it
holds kilometre-chainage differences** (verified values 0.17, 5.26, 5.2, 2.6 … km, i.e.
170–7,710 m). Writing them straight to `length_m` records a 5.26 km reach as **5.26 m — a
1000× error** — and the converter also injects default slopes/dimensions/lining instead of
joining `Characteristics`. **PR 2.1 must replace this with a strict multi-sheet generator**
(Sheet1 canonical nodes+chainage + Characteristics metre lengths+cross-sections + `สบ. 1`
structure levels/capacities) → a **versioned** network/geometry/calibration release keyed
to the workbook hash, **no silent hydraulic defaults**.

### 1.5 Calibration / device data — partial (provisional 2.3 only) `[xls:SCADA]`
Coverage over 59 gates (verified): **q_max 39/59, k1/k2/r² 10/59, coordinates 39/59, l1
18/59, l2–l4 16/59, l5 1/59, Sheet1.sill_level 0/59.** Sill/FSL/size/capacity live in
`สบ. 1` but **without a canonical M-id** (needs a reviewed canal/station join). Supports
provisional PR 2.3 inference; does **not** close E5 or production quantization.

---

## 2. Annual 2569 plan — a real allocation baseline, with defects `[xls:PLAN]`

Sheets: `แผนการส่งน้ำ 1-6` (plan), `น้ำเฉลี่ย ปี66`, `น้ำเฉลี่ย ปี39–ปี66`,
`ผลการส่งน้ำ 1-6` (result), `แผนการส่งน้ำ 1-6 ลบ.ม.` (plan in m³).

### 2.1 What it provides
Four rainy-season rotations with daily **zone-level rates** — Z1/Z2/Z3 = 1.5 m³/s, Z4/Z5 =
1.2, Z6 = 1.0 (rate cells verified present) — active-days per cycle 19/19/12/9/9/9; peak
project flow ~6.7 m³/s vs 11.2 m³/s head capacity. **Valuable for PR 2.4 (time-phased
allocation contract + m³→m³/s test), Wave 3.1 scheduler golden fixtures, capacity/
concurrency tests, and Wave 3.4 shadow-mode plan comparison.**

### 2.2 It is ALLOCATION, not demand — three concepts must stay separate
- **Agronomic demand** — crop water requirement (m³/period), by section.
- **Operator allocation** — what's released, where/when (m³/s over intervals), by zone.
- **Actual delivery** — gate/readback/flow-sensor evidence.
PR 2.4 must model all three; **PR 2.6 reconciles demand vs constrained allocation, never
overwrites one with the other.**

### 2.3 Defects to correct before any import (verified)
- **Year conflict:** filename + `ผลการส่งน้ำ` say **2569**; main plan + hidden `ลบ.ม.` titles
  say **2567** `[xls:PLAN]`. Importer cannot infer the year safely.
- **Date error:** Round 3 lists Sept 30 twice (…28,29,30,30,1,2…); dates stored as bare day
  numbers, no year/timezone.
- **Volume mismatch:** Rounds 2–4 populate 10 Zone-5 days while the duration/volume formulas
  use 9 → integrated daily cells 37,152,000 m³ vs summary 36,840,960 m³ = **311,040 m³
  understatement**.
- **Unit-label mismatch:** rate cells labelled `ลบ.ม.` (m³) but formulas × days × 86,400 s →
  actual unit is **m³/s**.
- **"Actual result" is prefilled:** `ผลการส่งน้ำ` holds first-cycle values though saved before
  the July-14 start — future/prefilled, **not measured delivery**.
- **Missing external source:** reservoir sheets link to `WaterDaily_อ่างฯมูลบน.xlsb`, not
  present locally → the workbook is **not** a portable source for current reservoir storage/
  inflow/release.

---

## 3. Live DB — area authority is now a top data risk `[DB]`

Four incompatible area totals for the same command area:

| Source | Area |
|--------|------|
| Annual plan basis | 45,000 rai |
| `gis.agricultural_plots` (15,069 parcels) | **44,441 rai** (verified) |
| Stale `weekly_water_demands` | 47,385 rai |
| SCADA section-labelled rows | 40,120 rai |

Per-section gaps are extreme (e.g. §22: 1,907 vs 663 rai; §9: 1,434 vs 578). **Until one
effective-dated area authority is chosen (RID/GIS/ROS), demand volumes and fairness are not
auditable.** Live GIS also: **all 15,069 parcels in a single zone** (one `zone_id` UUID,
none in zones 2–6), **no parcel `section_id`, all crop=rice, planting=1970-01-01**, and
**14 of 41 legacy `postgres.gis.zone` polygons invalid** `[DB]`. So: section→gate can come
from SCADA (§1.2); **parcel→section still needs repaired GIS assignment**; current crop/
planting-date truth is missing; the 327 `weekly_water_demands` rows remain a 6-second
synthetic backfill (rev. 2 §B.2).

---

## 4. Revised Wave 2–4 plan

### Wave 2
| PR | Status | Key gating |
|----|--------|-----------|
| **2.1** config generator | **Ready now — highest priority** | Build the strict multi-sheet generator (§1.4); do NOT reuse `excel_to_canal_sections.py` (1000× bug); output canonical ids as an *input* to 2.5 |
| **2.2** missing geometries | Conditionally ready | Acquisition mostly in `Characteristics`; needs the 59-edge coverage report + reviewed join (6 gates lack length) |
| **2.3** inferred calibration | Provisional only | 10/59 measured fits; not for actuation |
| **2.4** demand/allocation contract | **Materially unblocked** by the annual plan (after its defects are corrected) | Must separate demand/allocation/actual (§2.2) + own m³→m³/s conversion (rev. 2 §B.5) |
| **2.5** section-node map | **Reframed:** candidate crosswalk now available | Correct 1/2/40/42/43 renumbering + RID approval + versioned load; parcel→section still needs GIS |
| **2.6** demand producer | **Still blocked** | Crop/area/parcel lineage + weather + the non-runnable wired producer (rev. 2 §B.3) |
| **2.7** branch-split inverse | **Ready now** | independent hydraulic lane |
| **2.8** `/plan` observability | Ready after 2.7 | expose workbook version / coverage / confidence |
| **2.9** contract tests | Ready after 2.4 | |

### Wave 3
- **3.1 greedy scheduler** — algorithm work can use the annual plan as a **real golden baseline**; production needs RID-approved dates/priorities/section allocation.
- **3.2 travel-time** — prototype from the 99 `Characteristics` segments + `Experiment` velocities; `gate_mappings.travel_time_hours` stays *metadata/cache*, not the path calculation; field validation still required.
- **3.3 quantizer** — blocked by incomplete levels/calibration + **E5 device addressing** (`gate_configuration.json` = 7 gates, not 59).
- **3.4 shadow bridge** — plan-comparison design can start; real shadow op lacks commands/readbacks/actual flow/deployed identity; `integration_client.py` still unwired (missing `gis`/`ros` `base_urls` keys → KeyError).
- **3.5 CP-SAT** — defer.

### Wave 4 — plan-only
Workbooks improve geometry/history inputs but Wave 4 stays blocked by: stale water-level
telemetry (§ rev.2 C), no sensor→section/node registry (`gis.sensor_locations` = 1), no
current inflow/outflow series, no gate-state readback history, no observed 2569 delivery
data, no field seepage/travel-time campaign, missing current reservoir daily source.

---

## 5. Starting data still required (owner: RID/GIS/ROS)

**P0 — to close Wave 2:** (1) RID-approved **section master + crosswalk** (full code, numeric
suffix, zone, SCADA row, canonical M-id, primary/secondary semantics, effective date,
approver, workbook hash); (2) **corrected & approved 2569 plan** (resolve 2567/2569, dup
Sept 30, Zone-5 9-vs-10-day, 311,040 m³, explicit CE dates+TZ, version metadata); (3)
**parcel→section GIS assignment** (repair 14 invalid polygons, assign all 15,069 parcels,
fix all-one-zone, quarantine overlaps, record hashes); (4) **current 2569 crop register**
(plot/section, crop, area, planting/harvest, status, provenance); (5) **area-authority
decision**.

**P1 — for 2.6–3.4:** (6) current ROS/weather inputs (ETo, rainfall+source, effective-rain
method, Kc version, percolation, quality flags); (7) **reservoir daily source** (obtain
`WaterDaily_อ่างฯมูลบน.xlsb` or an API); (8) **SCADA device/address master — E5** (M-id →
PLC endpoint/protocol/registers/scaling/levels/authority/timeout/fail-safe); (9) **reach/
structure join approval** (M-edge→canal→chainage→Characteristics + sill/FSL/datum +
confidence); (10) actual operations history.

**P2 — before Wave 4:** (11) sensor registry + live section/node map; (12) field calibration
for the 49 inferred gates; (13) reach inflow/outflow seepage campaigns; (14) travel-time
observations; (15) formal allocation policy (priority/fairness/min-run/maintenance/override).

---

## 6. Recommended immediate sequence
1. RID review the inferred section corrections (§1.2).
2. Correct & approve the annual 2569 workbook (§2.3).
3. Start **PR 2.1** with the strict multi-sheet generator + workbook-hash provenance (§1.4).
4. Generate the 59-edge geometry coverage report for **PR 2.2**.
5. Amend **PR 2.4** to separate demand / allocation / actual.
6. Load approved sections + crosswalk in **PR 2.5**.
7. Run parcel→section GIS + current crop-season collection **in parallel**.
8. Only then rebuild the real demand producer in **PR 2.6**.
9. **PR 2.7 / 2.8** proceed independently the whole time.


---

## 7. CORRECTION (rev. 4, 2026-07-12): the 41-section MASTER exists — `postgres.gis.zone`

Rev. 3 (and my smart-cms-app pass) wrongly implied the section master was missing / that
`47,385` was a hardcoded mock. **Both wrong.** The authoritative 41-section master is the
`gis.zone` table **in the separate `postgres` database** (not `munbon_dev`) `[DB]`:

- **41 rows = 41 distinct section codes**, `code`/`props.Plot_id` in the live
  `01-ZZ-CC-SS` format, range **01-01-01-03 → 01-06-02-43** (6 zones, suffixes 03–43).
- Per section: **geometry (`geom`)**, **`Area_Rai`**, `NameArea` (canal+chainage, e.g.
  "4L-RMC 2+600 - 3+000"), `Zone`, admin location, land-use `Crop_1/Crop_2`.
- **`sum(Area_Rai) = 47,385 rai`** — THIS is the "47,385" figure; the smart-cms-app
  hardcoded fallback mirrors it, and the stale `weekly_water_demands` used it too.
- Quality gaps: **14/41 geometries invalid**; **`Plant_dat` null for all 41** (no current
  planting date); `Crop_1='นาข้าว'` is designed land-use, not current-season truth.

**Consumer:** the `smart-cms-app` frontend renders these 41 sections via the EC2
`scada-service` (`API_SERVER=http://<DB_HOST>` → `/scada-service/water-demand/weekly/{zone}/section`)
and a direct connection to `DB_NAME=postgres`. The map's per-section popups
(area, weekly demand) come from here, not the frontend's static geojson (which is only
7 unit polygons).

**Impact on Wave 2 — 2.5 is better-sourced than rev. 3 said:**
- Section MASTER (codes, area, geometry, canal/chainage) = `postgres.gis.zone` ✅ (repair
  14 geoms; add current crop-season).
- Section→gate crosswalk = SCADA Sheet1 (42/59) ✅.
- These **join** on canal+chainage/section identity. `munbon_dev.ros_gis.sections` (0) and
  `ros_gis.gate_mappings` (0) are the **destination** tables to populate FROM these two
  sources — not missing data, unpopulated pipeline.
- Still open: current crop-season register (Plant_dat null everywhere), parcel→section
  (`agricultural_plots` has no `section_id`), 14 invalid section geometries.

**Area authority (updated):** `47,385` (RID section master `postgres.gis.zone`, the
strongest section-level authority) vs `44,441` (parcels `agricultural_plots`) vs `40,120`
(SCADA section-labelled subset) vs `45,000` (plan) vs `58,066` (gross project units,
`moonbon_all_v7`). The section master is the natural authority for section-level demand;
the parcel/plan/gross figures differ by definition (parcels ⊂ command area ⊂ gross).

**smart-cms-app repos (two copies of `github.com/vitsanukomet/smart-cms-app`):**
`/Users/subhajlimanond/dev/smart-cms-app` = branch `dev`, 92 commits (HEAD `c296039`,
Jan 2026), has `.env.local` + **`.env.remote-wsl`**, cloned from GitHub 2026-06-01, last
active **2026-07-09** — the WSL-configured, active copy. `munbon2-frontend/smart-cms-app`
= 56 commits (HEAD `2119988`, Aug 2025) — an **ancestor** (its HEAD is `dev`'s merge-base),
36 commits behind, missing the section-detail / zone-sections / moisture / SV-sensor /
Section+Zone demand components. **Use `dev/smart-cms-app`.** Neither was git-cloned FROM the
munbon WSL (both origin = GitHub); the "wsl" link is the `.env.remote-wsl` pointing the
active copy at the EC2 backend.
