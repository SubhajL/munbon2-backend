#!/usr/bin/env bash
set -euo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/runtime-lib.sh"

load_runtime_env ros
require_env POSTGRES_URL REDIS_URL
SERVICE_ROOT="${REPO_ROOT}/services/ros-gis-integration"
service_python "${SERVICE_ROOT}"
cd "${SERVICE_ROOT}"

export PORT=3047 ENVIRONMENT=production LOG_LEVEL=INFO
export FLOW_MONITORING_URL=http://127.0.0.1:3011
export SCHEDULER_URL=http://127.0.0.1:3021
export SCHEDULER_SERVICE_URL=http://127.0.0.1:3021
export ROS_SERVICE_URL=http://127.0.0.1:3047
export GIS_SERVICE_URL=http://127.0.0.1:3007
export USE_MOCK_SERVER=false
export DAILY_REQUIREMENT_ENABLED=false
export DAILY_REQUIREMENT_STARTUP_CATCHUP_ENABLED=false
export DAILY_REQUIREMENT_SCHEDULE_ENABLED=false
unset REQUIREMENT_SOURCE_POSTGRES_URL
export CORS_ORIGINS=http://127.0.0.1:9999
export PYTHONPATH="${SERVICE_ROOT}/src"

"${PYTHON_BIN}" migrations/migrate.py apply 0001_dataset_version_parent
"${PYTHON_BIN}" migrations/migrate.py apply 0002_water_requirement_publication
"${PYTHON_BIN}" migrations/migrate.py apply 0003_daily_requirement_producer
exec "${PYTHON_BIN}" -m uvicorn src.main:app --host 127.0.0.1 --port 3047
