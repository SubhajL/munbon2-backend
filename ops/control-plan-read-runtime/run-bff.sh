#!/usr/bin/env bash
set -euo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/runtime-lib.sh"

load_runtime_env bff
require_env POSTGRES_URL REDIS_URL
SERVICE_ROOT="${REPO_ROOT}/services/bff-water-planning"
service_python "${SERVICE_ROOT}"
cd "${SERVICE_ROOT}"

export PORT=3022 ENVIRONMENT=production LOG_LEVEL=INFO
export FLOW_MONITORING_URL=http://127.0.0.1:3011
export SCHEDULER_URL=http://127.0.0.1:3021
export ROS_SERVICE_URL=http://127.0.0.1:3047
export GIS_SERVICE_URL=http://127.0.0.1:3007
export WEATHER_SERVICE_URL=http://127.0.0.1:3006
export WEATHER_API_URL=https://api.weather.example.com
export AWD_CONTROL_URL=http://127.0.0.1:3010
export SENSOR_DATA_URL=http://127.0.0.1:3003
export USE_MOCK_SERVER=false
export CORS_ORIGINS=http://127.0.0.1:9999
export DB_POOL_MIN_SIZE=1 DB_POOL_MAX_SIZE=5
export PYTHONPATH="${SERVICE_ROOT}/src"

"${PYTHON_BIN}" "${RUNTIME_DIR}/apply_bff_migration.py"
exec "${PYTHON_BIN}" -m uvicorn src.main:app --host 127.0.0.1 --port 3022
