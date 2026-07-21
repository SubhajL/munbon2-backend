#!/usr/bin/env bash
set -euo pipefail

RUNTIME_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${MUNBON_RUNTIME_GATE_PYTHON:-python3}"
BASELINE_FILE="$(mktemp /tmp/munbon-control-plan-baseline.XXXXXX)"
trap 'rm -f "${BASELINE_FILE}"' EXIT
cd "${RUNTIME_DIR}"

stop_runtime() {
  pm2 stop flow-monitoring scheduler ros-gis-integration bff-water-planning >/dev/null 2>&1 || true
}

"${PYTHON_BIN}" runtime_gate.py capacity
if ! pm2 start ecosystem.config.cjs --update-env; then
  stop_runtime
  exit 1
fi
if ! "${PYTHON_BIN}" runtime_gate.py snapshot >"${BASELINE_FILE}"; then
  stop_runtime
  exit 1
fi
if ! "${PYTHON_BIN}" runtime_gate.py stability --baseline "${BASELINE_FILE}" --startup-timeout 120 --duration 300 --interval 5; then
  stop_runtime
  exit 1
fi
pm2 save
