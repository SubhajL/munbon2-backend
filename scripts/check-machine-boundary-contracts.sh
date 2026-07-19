#!/usr/bin/env bash
# PR 6.0 — local cross-language machine-boundary contract gate.
# Runs the Python (jsonschema + pydantic) and the TypeScript (Ajv 2020) halves
# of the shared contracts/machine-boundary/v1 gate. Both assert the same manifest
# fixture vector and the same contract-set SHA-256, so both passing proves the
# two languages agree. It installs nothing, touches no database, and starts no
# service. E6 keeps GitHub Actions dormant, so this local run is PR evidence.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

echo "== scheduler (python: jsonschema + pydantic) =="
( cd "$ROOT/services/scheduler" \
  && PYTHONPATH=src ./venv/bin/python -m pytest -q \
       tests/unit/test_machine_boundary_contract.py )

echo "== scada-gate-control (typescript: Ajv 2020) =="
( cd "$ROOT/services/scada-gate-control" \
  && npx vitest run src/domain/machine-boundary-contract.spec.ts )

echo "== machine-boundary contract gate: OK =="
