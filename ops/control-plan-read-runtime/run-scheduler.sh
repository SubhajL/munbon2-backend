#!/usr/bin/env bash
set -euo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/runtime-lib.sh"

load_runtime_env scheduler
require_env POSTGRES_URL REDIS_URL JWT_SECRET_KEY JWT_ISSUER JWT_AUDIENCE JWT_CLAIM_POLICY_MODE
SERVICE_ROOT="${REPO_ROOT}/services/scheduler"
service_python "${SERVICE_ROOT}"
cd "${SERVICE_ROOT}"

export PORT=3021 SERVICE_PORT=3021 ENVIRONMENT=production LOG_LEVEL=INFO
export FLOW_MONITORING_URL=http://127.0.0.1:3011
export ROS_GIS_URL=http://127.0.0.1:3047
export ROS_SERVICE_URL=http://127.0.0.1:3047
export GIS_SERVICE_URL=http://127.0.0.1:3007
export WEATHER_SERVICE_URL=http://127.0.0.1:3006
export AUTH_SERVICE_URL=http://127.0.0.1:3005
export JWT_ACCESS_TOKEN_TYPE=access
export CONTROL_EXECUTION_MODE=disabled
export CONTROL_READBACK_RECONCILIATION_MODE=off
unset SCHEDULER_SCADA_BASE_URL SCHEDULER_SERVICE_JWT_SECRET SCHEDULER_DEVICE_CAPABILITY_SNAPSHOT_PATH
export PYTHONPATH="${SERVICE_ROOT}/src"

"${PYTHON_BIN}" migrations/migrate.py apply-all
exec "${PYTHON_BIN}" -m uvicorn src.main:app --host 127.0.0.1 --port 3021
