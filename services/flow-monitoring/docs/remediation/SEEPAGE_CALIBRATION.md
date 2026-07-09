# B5 Seepage Calibration — aged concrete-lined canals

**Date:** 2026-07-09 · **Scope:** the `SEEPAGE_RATE_BY_LINING` and `operational_loss_frac`
defaults in `src/core/conveyance_loss.py`. **Status:** PROVISIONAL — literature field values,
pending a Munbon Tier-3 inflow/outflow calibration.

## Why this changed
B5 originally shipped with `concrete = 3.0e-7 m/s` (a **new**-concrete design standard) plus a
flat **5% per-reach** operational loss. Two problems surfaced:
1. The Munbon canals are **~50 years old** — new-concrete seepage standards do not apply.
2. The per-reach 5% operational fraction is **discretization-dependent** (it compounds with the
   number of gate nodes, so subdividing a canal into more reaches inflates modeled loss — a
   modeling artifact, not physics). It produced ~+55–90% aggregate loss.

## New defaults
| Lining | Old (new-concrete) | New (aged field) | Basis |
|---|---|---|---|
| concrete | 3.0e-7 m/s | **1.0e-5 m/s** | aged Turkey field central (~1e-5) |
| earth | 1.5e-6 m/s | **2.0e-5 m/s** | unlined field; kept > aged concrete |
| unknown | 1.0e-6 m/s | **1.5e-5 m/s** | conservative middle |
| `operational_loss_frac` | 0.05 (per reach) | **0.0** | seepage is the dominant loss; drop the discretization-dependent term (stays a per-section knob) |

## Sources (verified 2026-07-09 by direct fetch — see note)
| Value | Source |
|---|---|
| **New** concrete standard 0.00024 L/s/m² = **2.4e-7 m/s** (USBR 1975); FAO/Kraatz 1977 ~3e-7 | Akkuzu et al., *Determination of Water Conveyance Loss in the Menemen Open Canal Irrigation Network*, Turkish J. Ag. For. 31(1):11–22 |
| **Aged** concrete field seepage **0.0026–0.0754 L/s/m² = 2.6e-6 … 7.5e-5 m/s** (Bekifloğlu 1993) | ” |
| Aged Ahmetli concrete **main 0.067 L/s/m² = 6.7e-5 m/s** | Kılıç & Tuylu, *Ahmetli Regulator…*, Irrig. & Drainage (Wiley) 10.1002/ird.602 |
| Menemen concrete **main 107.6 L/s/km** (aged) | Akkuzu, *Usefulness of Empirical Equations…*, ASCE J. Irrig. Drain. Eng. 10.1061/(ASCE)IR.1943-4774.0000414 |
| *"Seepage is the most dominant process by which water is lost"* | ” |
| Lined canal **95% conveyance efficiency**; *"bad maintenance may lower … by as much as 50%"* | FAO Irrigation Water Management Training Manual, Annex I, Table 7 (fao.org/4/t7202e/t7202e08.htm) |
| Aged lining loses efficacy with service time; unmaintained concrete approaches unlined | MDPI *Water* 12(9):2343 (Han et al. 2020); Plusquellec 2019, Irrig. & Drainage 10.1002/ird.2341 |

## Sanity check (encoded as a test)
With the calibrated `1e-5 m/s`, delivering the LMC design flow (8.737 m³/s) to the tail
`M(0,12)` loses **~2.46 m³/s ≈ 68 L/s/km ≈ 22–28%** over the ~36 km LMC — inside the aged-field
band (new ~10 → aged Menemen ~108 L/s/km). Guarded by
`test_lmc_seepage_per_km_is_in_the_aged_concrete_field_range` (asserts 20–120 L/s/km, so it
rejects both the too-low new-concrete rate and an implausibly high one).

## Caveats
- **Provisional.** These are literature values for *comparable aged systems*, not Munbon
  measurements. The real fix is a **Tier-3 inflow/outflow calibration** on Munbon reaches
  (`seepage_rate ≈ (Q_in − Q_out)/(P·L)` per lining class), which overwrites these defaults.
- **Verification note:** the automated deep-research verify pass rate-limited out (resets
  2026-07-11); the values above were confirmed by **direct fetch** of the FAO page and the
  primary studies (via exa) on 2026-07-09. A re-run of the adversarial verifier after Jul 11
  can add a second confirmation layer.
- Field seepage is **highly variable** (Menemen coefficients of variation 73–158%), so a single
  rate is a coarse descriptor; treat it as an order-of-magnitude default until calibrated.
