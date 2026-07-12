# Gate calibration configuration

`src/config/gate_calibrations.json` is generated from the committed SCADA workbook by
`scripts/build_scada_config.py`. The generator is the only supported producer; the old
standalone extraction scripts were removed because they emitted incompatible schemas.

The configuration contains all 59 canonical gates and records these fields per gate:

- `calibration_method`: `measured`, `inferred`, or `default`
- `confidence`: the Sheet1 `r2` value for measured coefficients
- `source_gate_ids`: the measured gate itself, measured donor gates for an inference,
  or an empty list for a default
- `source_version`: the version of the coefficient source
- `k1` and `k2`: required for measured and inferred records, forbidden for defaults

The current workbook provides 10 measured `k1`/`k2`/`r2` triplets. The remaining 49
records are explicit defaults until the Wave 2.3 similar-gate calibration is generated.
`utils/gate_calibration_loader.py` preserves the three methods and uses supplied inferred
coefficients instead of routing them through the default ladder.

Regenerate all canonical SCADA artifacts together:

```bash
cd services/flow-monitoring
./venv/bin/python scripts/build_scada_config.py
```

The unit suite regenerates `gate_calibrations.json` from the committed workbook and
compares bytes, so hand edits and stale output fail the service gate.
