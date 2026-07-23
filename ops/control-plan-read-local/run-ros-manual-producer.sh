#!/usr/bin/env bash
set -euo pipefail

RUNTIME_ENV_DIR="${MUNBON_RUNTIME_ENV_DIR:-/etc/munbon/control-plan-read-runtime}"
ROS_ENV="${RUNTIME_ENV_DIR}/ros.env"
LOCAL_SECRETS_ENV="${RUNTIME_ENV_DIR}/local-secrets.env"
if [[ ! -r "${ROS_ENV}" || ! -r "${LOCAL_SECRETS_ENV}" ]]; then
  echo "FAIL ros_manual_environment" >&2
  exit 1
fi

set -a
source "${ROS_ENV}"
source "${LOCAL_SECRETS_ENV}"
set +a
if [[ -z "${DAILY_REQUIREMENT_MANUAL_TOKEN:-}" ]]; then
  echo "FAIL ros_manual_token" >&2
  exit 1
fi

export DAILY_REQUIREMENT_ENABLED=true
export DAILY_REQUIREMENT_STARTUP_CATCHUP_ENABLED=false
export DAILY_REQUIREMENT_SCHEDULE_ENABLED=false
export REQUIREMENT_SOURCE_POSTGRES_URL="${POSTGRES_URL}"
export FLOW_MONITORING_URL=http://127.0.0.1:3011
export USE_MOCK_SERVER=false
export ALLOW_MACHINE_COMMANDS=false

SERVICE_ROOT=/opt/munbon/repo/services/ros-gis-integration
export PYTHONPATH="${SERVICE_ROOT}/src"
cd "${SERVICE_ROOT}"
exec .venv/bin/uvicorn src.main:app --host 127.0.0.1 --port 3047
