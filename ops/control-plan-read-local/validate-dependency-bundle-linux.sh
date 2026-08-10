#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" != "0" || "$#" != "5" || "$(uname -m)" != "aarch64" ]]; then
  printf '%s\n' "FAIL dependency_validation_arguments" >&2
  exit 2
fi

BUNDLE_ROOT="$1"
REPO_ROOT="$2"
FRONTEND_ROOT="$3"
RELEASE_SHA="$4"
FRONTEND_SHA="$5"
SCRATCH_ROOT="$(mktemp -d)"

cleanup() {
  rm -rf "${SCRATCH_ROOT}"
}
trap cleanup EXIT

for package in "${BUNDLE_ROOT}"/debian/*.deb; do
  dpkg-deb --info "${package}" >/dev/null
done

APT_STATUS="${SCRATCH_ROOT}/apt-status"
APT_LISTS="${SCRATCH_ROOT}/apt-lists"
APT_ARCHIVES="${SCRATCH_ROOT}/apt-archives"
: > "${APT_STATUS}"
mkdir -p "${APT_LISTS}/partial" "${APT_ARCHIVES}/partial"
apt-get --simulate --no-download --no-install-recommends \
  -o "Dir::State::status=${APT_STATUS}" \
  -o "Dir::State::lists=${APT_LISTS}" \
  -o "Dir::Cache::archives=${APT_ARCHIVES}" \
  -o Dir::Etc::sourcelist=/dev/null \
  -o Dir::Etc::sourceparts=- \
  install "${BUNDLE_ROOT}"/debian/*.deb >/dev/null

mkdir -p "${SCRATCH_ROOT}/node"
tar -xJf "${BUNDLE_ROOT}/node-v22.23.1-linux-arm64.tar.xz" \
  --strip-components=1 --directory="${SCRATCH_ROOT}/node"
NODE_ROOT="${SCRATCH_ROOT}/node"
if [[ \
  "$("${SCRATCH_ROOT}/node/bin/node" --version)" != "v22.23.1" \
  || "$("${SCRATCH_ROOT}/node/bin/npm" --version)" != "10.9.8" \
]]; then
  printf '%s\n' "FAIL dependency_validation_node" >&2
  exit 1
fi

validate_npm_lock() {
  local source_root="$1"
  local name="$2"
  shift 2
  local target_root="${SCRATCH_ROOT}/npm/${name}"
  mkdir -p "${target_root}"
  cp "${source_root}/package.json" "${source_root}/package-lock.json" "${target_root}/"
  if [[ "${name}" == "auth" ]]; then
    mkdir -p "${SCRATCH_ROOT}/shared/nodejs"
    cp -R "${REPO_ROOT}/shared/nodejs/." "${SCRATCH_ROOT}/shared/nodejs/"
  fi
  python3 "${REPO_ROOT}/ops/control-plan-read-local/provisioning_contract.py" \
    validate-node-archive \
    --name "${name}" \
    --archive "${BUNDLE_ROOT}/node-modules/${name}.tar.gz"
  tar -xzf "${BUNDLE_ROOT}/node-modules/${name}.tar.gz" \
    --directory "${target_root}"
  if [[ "${name}" != "auth" && "${name}" != "frontend" ]]; then
    env PATH="${NODE_ROOT}/bin:/usr/bin:/bin" npm_config_offline=true \
      "${NODE_ROOT}/bin/npm" --prefix "${target_root}" ls --all "$@" >/dev/null
  fi
}

validate_npm_lock "${REPO_ROOT}/services/auth" auth --omit=dev
validate_npm_lock "${REPO_ROOT}/infra/pm2" pm2
validate_npm_lock "${REPO_ROOT}/services/scada-gate-control" scada
validate_npm_lock "${REPO_ROOT}/services/scada-gate-control-web" gate-web
validate_npm_lock "${FRONTEND_ROOT}" frontend
validate_npm_lock \
  "${REPO_ROOT}/ops/control-plan-read-local/dependency-roots" dependency-roots
test -f "${SCRATCH_ROOT}/npm/frontend/node_modules/.prisma/client/index.js"
find "${SCRATCH_ROOT}/npm/auth/node_modules" -type f -name '*.node' -print -quit \
  | grep -q .
(
  cd "${SCRATCH_ROOT}/npm/auth"
  "${NODE_ROOT}/bin/node" -e "require('bcrypt')"
)
(
  cd "${SCRATCH_ROOT}/npm/frontend"
  "${NODE_ROOT}/bin/node" -e "require('@prisma/client')"
)

for service in flow-monitoring scheduler ros-gis-integration bff-water-planning; do
  python3 -m venv "${SCRATCH_ROOT}/python-${service}"
  "${SCRATCH_ROOT}/python-${service}/bin/pip" install \
    --disable-pip-version-check --no-index \
    --find-links "${BUNDLE_ROOT}/python/${service}" \
    --requirement "${REPO_ROOT}/services/${service}/requirements.txt"
  "${SCRATCH_ROOT}/python-${service}/bin/python" -m pip check
done

test -x "${BUNDLE_ROOT}/playwright-browsers/chromium-*/chrome-linux/chrome" \
  || find "${BUNDLE_ROOT}/playwright-browsers" -type f -name chrome -perm -u+x \
    -print -quit | grep -q .

printf '%s\n' \
  "PASS dependency_validation ${RELEASE_SHA} ${FRONTEND_SHA} node-modules python playwright-browsers"
