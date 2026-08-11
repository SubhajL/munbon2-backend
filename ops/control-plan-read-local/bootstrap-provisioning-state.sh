#!/usr/bin/env bash
set -euo pipefail

validate_bootstrap_state_fields() {
  local state="$1"
  local release_sha="$2"
  local frontend_sha="$3"
  local dependency_sha256="$4"
  local phase="$5"
  local substep="$6"

  if [[ \
    ! "${state}" =~ ^(created|failed|interrupted)$ \
    || ! "${release_sha}" =~ ^[0-9a-f]{40}$ \
    || ! "${frontend_sha}" =~ ^[0-9a-f]{40}$ \
    || ! "${dependency_sha256}" =~ ^[0-9a-f]{64}$ \
    || ! "${phase}" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ \
    || ! "${substep}" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ \
  ]]; then
    return 1
  fi
}

write_bootstrap_state() {
  local state_root="$1"
  local state="$2"
  local release_sha="$3"
  local frontend_sha="$4"
  local dependency_sha256="$5"
  local phase="$6"
  local substep="$7"
  local recorded_at
  local temporary

  validate_bootstrap_state_fields \
    "${state}" "${release_sha}" "${frontend_sha}" "${dependency_sha256}" \
    "${phase}" "${substep}"
  recorded_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  install -d -m 0700 "${state_root}"
  temporary="${state_root}/.state.json.$$"
  if [[ -e "${temporary}" ]]; then
    return 1
  fi
  printf '%s\n' \
    '{' \
    "  \"dependency_sha256\": \"${dependency_sha256}\"," \
    "  \"frontend_sha\": \"${frontend_sha}\"," \
    "  \"phase\": \"${phase}\"," \
    "  \"recorded_at\": \"${recorded_at}\"," \
    "  \"release_sha\": \"${release_sha}\"," \
    "  \"state\": \"${state}\"," \
    "  \"substep\": \"${substep}\"" \
    '}' > "${temporary}"
  chmod 600 "${temporary}"
  mv -- "${temporary}" "${state_root}/state.json"
}

write_pre_python_failure() {
  local state_root="$1"
  local release_sha="$2"
  local frontend_sha="$3"
  local dependency_sha256="$4"
  local phase="$5"
  local substep="$6"
  local exit_code="$7"
  local interrupted="$8"
  local state=failed
  local classification=nonretryable-bootstrap
  local bash_version
  local recorded_at
  local temporary

  if [[ ! "${exit_code}" =~ ^[0-9]+$ ]] \
    || (( exit_code < 1 || exit_code > 255 )) \
    || [[ ! "${interrupted}" =~ ^(true|false)$ ]]; then
    return 1
  fi
  if [[ "${interrupted}" == "true" ]]; then
    state=interrupted
    classification=interrupted
  elif [[ "${phase}" == "dependency_archive" ]]; then
    classification=nonretryable-integrity
  fi
  validate_bootstrap_state_fields \
    "${state}" "${release_sha}" "${frontend_sha}" "${dependency_sha256}" \
    "${phase}" "${substep}"
  if [[ -e "${state_root}/failure" ]]; then
    return 1
  fi
  write_bootstrap_state \
    "${state_root}" "${state}" "${release_sha}" "${frontend_sha}" \
    "${dependency_sha256}" "${phase}" "${substep}"
  recorded_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  bash_version="${BASH_VERSION%%\(*}"
  temporary="${state_root}/.failure.$$"
  install -d -m 0700 "${temporary}"
  printf 'FAIL bootstrap_%s\n' "${phase}" \
    > "${temporary}/bootstrap-sanitized.log"
  printf '%s\n' \
    '{' \
    "  \"classification\": \"${classification}\"," \
    "  \"dependency_sha256\": \"${dependency_sha256}\"," \
    "  \"exit_code\": ${exit_code}," \
    "  \"frontend_sha\": \"${frontend_sha}\"," \
    "  \"phase\": \"${phase}\"," \
    "  \"recorded_at\": \"${recorded_at}\"," \
    "  \"release_sha\": \"${release_sha}\"," \
    "  \"state\": \"${state}\"," \
    "  \"substep\": \"${substep}\"," \
    '  "tool_versions": {' \
    "    \"bash\": \"${bash_version}\"" \
    '  }' \
    '}' > "${temporary}/metadata.json"
  (
    cd "${temporary}"
    sha256sum bootstrap-sanitized.log metadata.json > SHA256SUMS
  )
  chmod 600 \
    "${temporary}/bootstrap-sanitized.log" \
    "${temporary}/metadata.json" \
    "${temporary}/SHA256SUMS"
  mv -- "${temporary}" "${state_root}/failure"
}

write_bootstrap_failure() {
  local state_root="$1"
  local release_sha="$2"
  local frontend_sha="$3"
  local dependency_sha256="$4"
  local phase="$5"
  local substep="$6"
  local exit_code="$7"
  local interrupted="$8"
  local log_path="$9"
  local contract_writer="${10}"
  local contract_script="${11}"
  local node_root="${12}"
  local interrupted_option=

  if [[ "${interrupted}" == "true" ]]; then
    interrupted_option=--interrupted
  fi
  if [[ -x "${contract_writer}" && -f "${contract_script}" ]] \
    && "${contract_writer}" "${contract_script}" failure \
      --state-root "${state_root}" \
      --release-sha "${release_sha}" \
      --frontend-sha "${frontend_sha}" \
      --dependency-sha256 "${dependency_sha256}" \
      --phase "${phase}" \
      --substep "${substep}" \
      --exit-code "${exit_code}" \
      --log "${log_path}" \
      --tool-version "bash=${BASH_VERSION%%\(*}" \
      --tool-version "node=$("${node_root}/bin/node" --version 2>/dev/null || printf unknown)" \
      --tool-version "npm=$(env PATH="${node_root}/bin:/usr/bin:/bin" \
        "${node_root}/bin/npm" --version 2>/dev/null || printf unknown)" \
      --tool-version "python=$("${contract_writer}" --version 2>&1 | awk '{print $2}' || printf unknown)" \
      ${interrupted_option:+"${interrupted_option}"} >/dev/null 2>&1; then
    return 0
  fi
  write_pre_python_failure \
    "${state_root}" "${release_sha}" "${frontend_sha}" \
    "${dependency_sha256}" "${phase}" "${substep}" "${exit_code}" \
    "${interrupted}"
}
