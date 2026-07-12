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

The workbook provides 10 measured `k1`/`k2`/`r2` triplets. The other 49 records are
provisional similar-gate inferences for planning only. The generator ranks measured donors
by physical shape, dimension similarity, and canal class, then confidence-weights the top
three coefficients. Inferred confidence includes a similarity penalty and must be lower
than every cited measured donor. Circular gates currently cite one donor because the
workbook contains only one measured circular gate; that limitation remains explicit in
`source_gate_ids` and confidence.

`utils/gate_calibration_loader.py` preserves measured/inferred/default methods, consumes
inferred coefficients instead of routing them through the default ladder, and exposes the
bundle's `planning_only` intended use. The strict loader rejects invalid lineage, source-
version drift, or inferred confidence that is not lower than its donors.

Regenerate all canonical SCADA artifacts together:

```bash
cd services/flow-monitoring
./venv/bin/python scripts/build_scada_config.py
```

The unit suite regenerates `gate_calibrations.json` from the committed workbook and
compares bytes, so hand edits and stale output fail the service gate.
