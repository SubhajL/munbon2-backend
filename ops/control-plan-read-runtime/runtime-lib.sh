#!/usr/bin/env bash
set -euo pipefail

RUNTIME_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${RUNTIME_DIR}/../.." && pwd)"
ENV_DIR="${MUNBON_RUNTIME_ENV_DIR:-/etc/munbon/control-plan-read-runtime}"

load_runtime_env() {
  local service_name="$1"
  local env_file="${ENV_DIR}/${service_name}.env"
  if [[ ! -f "${env_file}" ]]; then
    echo "Runtime env file missing for ${service_name}" >&2
    return 1
  fi
  local mode
  mode="$(stat -c '%a' "${env_file}" 2>/dev/null || stat -f '%Lp' "${env_file}")"
  if [[ "${mode}" != "600" ]]; then
    echo "Runtime env file must have mode 600 for ${service_name}" >&2
    return 1
  fi
  set -a
  # The mode-600 file is trusted operator-owned shell environment configuration.
  source "${env_file}"
  set +a
}

require_env() {
  local name
  for name in "$@"; do
    if [[ -z "${!name:-}" ]]; then
      echo "Required runtime setting is missing: ${name}" >&2
      return 1
    fi
  done
}

service_python() {
  local service_root="$1"
  PYTHON_BIN="${service_root}/.venv/bin/python"
  if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "Tracked service environment is missing: ${service_root}/.venv" >&2
    return 1
  fi
}
