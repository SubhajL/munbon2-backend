#!/usr/bin/env bash
set -euo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/runtime-lib.sh"

load_runtime_env flow
require_env POSTGRES_URL TIMESCALE_URL REDIS_URL INFLUXDB_URL INFLUXDB_TOKEN INFLUXDB_ORG INFLUXDB_BUCKET
SERVICE_ROOT="${REPO_ROOT}/services/flow-monitoring"
service_python "${SERVICE_ROOT}"
cd "${SERVICE_ROOT}"

export PORT=3011 ENVIRONMENT=production LOG_LEVEL=INFO
export GATES_API_ENABLED=false
export HYDRAULIC_MODEL_RELEASE_PATH=data/model-releases/engineering-prior-v3-v1.json
export CORS_ORIGINS=http://127.0.0.1:9999
export PYTHONPATH="${SERVICE_ROOT}/src"

"${PYTHON_BIN}" migrations/migrate.py apply-all
exec "${PYTHON_BIN}" -m uvicorn src.main:app --host 127.0.0.1 --port 3011
