#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" != "0" || "$#" != "8" || "$(uname -m)" != "aarch64" ]]; then
  printf '%s\n' "FAIL dependency_bundle_arguments" >&2
  exit 2
fi

SOURCE_BUNDLE="$1"
RELEASE_SHA="$2"
FRONTEND_BUNDLE="$3"
FRONTEND_SHA="$4"
CONTRACT_SCRIPT="$5"
VALIDATOR_SCRIPT="$6"
INSTALLER_SCRIPT="$7"
OUTPUT_ARCHIVE="$8"
NODE_VERSION=22.23.1
NPM_VERSION=10.9.8
PLAYWRIGHT_VERSION=1.54.2
INFLUX_FINGERPRINT=24C975CBA61A024EE1B631787C3D57159FC2F927
BUILD_ROOT="$(mktemp -d)"

cleanup() {
  rm -rf "${BUILD_ROOT}"
}
trap cleanup EXIT

if [[ \
  ! "${RELEASE_SHA}" =~ ^[0-9a-f]{40}$ \
  || ! "${FRONTEND_SHA}" =~ ^[0-9a-f]{40}$ \
  || ! -f "${SOURCE_BUNDLE}" \
  || ! -f "${FRONTEND_BUNDLE}" \
  || ! -f "${CONTRACT_SCRIPT}" \
  || ! -f "${VALIDATOR_SCRIPT}" \
  || ! -f "${INSTALLER_SCRIPT}" \
  || ! -x "$(command -v dpkg-scanpackages)" \
  || -e "${OUTPUT_ARCHIVE}" \
  || "$(. /etc/os-release && printf '%s' "${ID}")" != "debian" \
  || "$(. /etc/os-release && printf '%s' "${VERSION_ID}")" != "12" \
]]; then
  printf '%s\n' "FAIL dependency_bundle_inputs" >&2
  exit 1
fi

REPO_ROOT="${BUILD_ROOT}/repo"
FRONTEND_ROOT="${BUILD_ROOT}/frontend"
BUNDLE_ROOT="${BUILD_ROOT}/bundle"
NODE_ROOT="${BUILD_ROOT}/node"
NPM_CACHE="${BUILD_ROOT}/npm-cache"
mkdir -p "${BUNDLE_ROOT}/debian" "${BUNDLE_ROOT}/python" \
  "${BUNDLE_ROOT}/playwright-browsers" "${BUNDLE_ROOT}/node-modules" \
  "${NPM_CACHE}"

git clone --quiet "${SOURCE_BUNDLE}" "${REPO_ROOT}"
git -C "${REPO_ROOT}" checkout --force --quiet --detach "${RELEASE_SHA}"
git clone --quiet "${FRONTEND_BUNDLE}" "${FRONTEND_ROOT}"
git -C "${FRONTEND_ROOT}" checkout --force --quiet --detach "${FRONTEND_SHA}"

NODE_ARCHIVE="node-v${NODE_VERSION}-linux-arm64.tar.xz"
curl --fail --silent --show-error --location \
  "https://nodejs.org/dist/v${NODE_VERSION}/${NODE_ARCHIVE}" \
  --output "${BUNDLE_ROOT}/${NODE_ARCHIVE}"
curl --fail --silent --show-error --location \
  "https://nodejs.org/dist/v${NODE_VERSION}/SHASUMS256.txt" \
  --output "${BUILD_ROOT}/NODE-SHA256SUMS"
(
  cd "${BUNDLE_ROOT}"
  grep " ${NODE_ARCHIVE}$" "${BUILD_ROOT}/NODE-SHA256SUMS" \
    | sha256sum --check --status
)
mkdir -p "${NODE_ROOT}"
tar -xJf "${BUNDLE_ROOT}/${NODE_ARCHIVE}" \
  --strip-components=1 --directory="${NODE_ROOT}"
if [[ \
  "$("${NODE_ROOT}/bin/node" --version)" != "v${NODE_VERSION}" \
  || "$(env PATH="${NODE_ROOT}/bin:/usr/bin:/bin" \
    "${NODE_ROOT}/bin/npm" --version)" != "${NPM_VERSION}" \
]]; then
  printf '%s\n' "FAIL dependency_bundle_node_version" >&2
  exit 1
fi

stage_npm_tree() {
  local root="$1"
  local name="$2"
  shift 2
  test -f "${root}/package-lock.json"
  env PATH="${NODE_ROOT}/bin:/usr/bin:/bin" \
    "${NODE_ROOT}/bin/npm" --prefix "${root}" ci \
    --audit=false --fund=false \
    --cache "${NPM_CACHE}" "$@"
  if [[ "${name}" == "frontend" ]]; then
    (
      cd "${root}"
      env PATH="${NODE_ROOT}/bin:/usr/bin:/bin" \
        "${NODE_ROOT}/bin/npm" exec prisma generate
    )
  fi
  if [[ "${name}" != "auth" && "${name}" != "frontend" ]]; then
    env PATH="${NODE_ROOT}/bin:/usr/bin:/bin" \
      "${NODE_ROOT}/bin/npm" --prefix "${root}" ls --all "$@" >/dev/null
  fi
  tar -C "${root}" --sort=name --mtime='UTC 1970-01-01' \
    --owner=0 --group=0 --numeric-owner -cf - node_modules \
    | gzip -n > "${BUNDLE_ROOT}/node-modules/${name}.tar.gz"
  python3 "${CONTRACT_SCRIPT}" validate-node-archive \
    --name "${name}" \
    --archive "${BUNDLE_ROOT}/node-modules/${name}.tar.gz"
  rm -rf "${root}/node_modules"
}

stage_npm_tree "${REPO_ROOT}/services/auth" auth --omit=dev
stage_npm_tree "${REPO_ROOT}/infra/pm2" pm2
stage_npm_tree "${REPO_ROOT}/services/scada-gate-control" scada
stage_npm_tree "${REPO_ROOT}/services/scada-gate-control-web" gate-web
stage_npm_tree "${FRONTEND_ROOT}" frontend

python3 -m venv "${BUILD_ROOT}/wheel-builder"
for service in flow-monitoring scheduler ros-gis-integration bff-water-planning; do
  mkdir -p "${BUNDLE_ROOT}/python/${service}"
  "${BUILD_ROOT}/wheel-builder/bin/python" -m pip wheel \
    --disable-pip-version-check \
    --wheel-dir "${BUNDLE_ROOT}/python/${service}" \
    --requirement "${REPO_ROOT}/services/${service}/requirements.txt"
done

PYTHON_CLOSURE_COUNT=0
while read -r service expected_digest expected_count; do
  [[ \
    "${service}" =~ ^[a-z0-9-]+$ \
    && "${expected_digest}" =~ ^[0-9a-f]{64}$ \
    && "${expected_count}" =~ ^[0-9]+$ \
  ]] || exit 1
  wheel_root="${BUNDLE_ROOT}/python/${service}"
  actual_count="$(find "${wheel_root}" -maxdepth 1 -type f -name '*.whl' | wc -l | tr -d ' ')"
  actual_digest="$(
    cd "${wheel_root}"
    find . -maxdepth 1 -type f -name '*.whl' -print0 \
      | LC_ALL=C sort -z \
      | xargs -0 sha256sum \
      | sha256sum \
      | awk '{print $1}'
  )"
  if [[ \
    "${actual_count}" != "${expected_count}" \
    || "${actual_digest}" != "${expected_digest}" \
  ]]; then
    printf '%s\n' "FAIL dependency_bundle_python_closure" >&2
    exit 1
  fi
  PYTHON_CLOSURE_COUNT=$((PYTHON_CLOSURE_COUNT + 1))
done < "${REPO_ROOT}/ops/control-plan-read-local/python-closures.lock"
if [[ "${PYTHON_CLOSURE_COUNT}" != "4" ]]; then
  printf '%s\n' "FAIL dependency_bundle_python_closure_inventory" >&2
  exit 1
fi

DEPENDENCY_ROOT="${REPO_ROOT}/ops/control-plan-read-local/dependency-roots"
env PATH="${NODE_ROOT}/bin:/usr/bin:/bin" \
  "${NODE_ROOT}/bin/npm" --prefix "${DEPENDENCY_ROOT}" ci \
  --audit=false --fund=false --cache "${NPM_CACHE}"
PLAYWRIGHT_CLI="${DEPENDENCY_ROOT}/node_modules/playwright/cli.js"
PLAYWRIGHT_BROWSERS_PATH="${BUNDLE_ROOT}/playwright-browsers" \
  "${NODE_ROOT}/bin/node" "${PLAYWRIGHT_CLI}" install chromium
PLAYWRIGHT_DEPENDENCY_COMMAND="$(
  "${NODE_ROOT}/bin/node" "${PLAYWRIGHT_CLI}" install-deps --dry-run chromium
)"
if [[ "${PLAYWRIGHT_DEPENDENCY_COMMAND}" != *"apt-get install -y --no-install-recommends"* ]]; then
  printf '%s\n' "FAIL dependency_bundle_playwright_deps" >&2
  exit 1
fi
PLAYWRIGHT_DEPENDENCIES="${PLAYWRIGHT_DEPENDENCY_COMMAND#*--no-install-recommends }"
PLAYWRIGHT_DEPENDENCIES="${PLAYWRIGHT_DEPENDENCIES%\"}"
env PATH="${NODE_ROOT}/bin:/usr/bin:/bin" \
  "${NODE_ROOT}/bin/npm" --prefix "${DEPENDENCY_ROOT}" ls --all >/dev/null
tar -C "${DEPENDENCY_ROOT}" --sort=name --mtime='UTC 1970-01-01' \
  --owner=0 --group=0 --numeric-owner -cf - node_modules \
  | gzip -n > "${BUNDLE_ROOT}/node-modules/dependency-roots.tar.gz"
python3 "${CONTRACT_SCRIPT}" validate-node-archive \
  --name dependency-roots \
  --archive "${BUNDLE_ROOT}/node-modules/dependency-roots.tar.gz"
rm -rf "${DEPENDENCY_ROOT}/node_modules"

mkdir -p /etc/apt/keyrings
INFLUX_KEY="${BUILD_ROOT}/influxdata-archive.key"
curl --fail --silent --show-error --location \
  https://repos.influxdata.com/influxdata-archive.key --output "${INFLUX_KEY}"
if ! gpg --show-keys --with-fingerprint --with-colons "${INFLUX_KEY}" 2>/dev/null \
  | grep -q "^fpr:::::::::${INFLUX_FINGERPRINT}:$"; then
  printf '%s\n' "FAIL dependency_bundle_influx_key" >&2
  exit 1
fi
cp "${INFLUX_KEY}" "${BUNDLE_ROOT}/influxdata-archive.key"
gpg --dearmor --yes --output /etc/apt/keyrings/influxdata-archive.gpg "${INFLUX_KEY}"
printf '%s\n' \
  'deb [signed-by=/etc/apt/keyrings/influxdata-archive.gpg] https://repos.influxdata.com/debian stable main' \
  > /etc/apt/sources.list.d/influxdata.list
apt-get update -qq

read -r -a PLAYWRIGHT_PACKAGES <<< "${PLAYWRIGHT_DEPENDENCIES}"
APT_ROOTS=(
  build-essential ca-certificates coinor-cbc curl gdal-bin git gnupg jq
  libgdal-dev libgeos-dev libpq-dev openssl postgresql postgresql-contrib
  postgresql-15-postgis-3 prometheus python3 python3-dev python3-venv redis-server rsync
  xz-utils influxdb2 "${PLAYWRIGHT_PACKAGES[@]}"
)
APT_STATUS="${BUILD_ROOT}/apt-status"
: > "${APT_STATUS}"
mkdir -p "${BUNDLE_ROOT}/debian/partial"
apt-get --yes --download-only --no-install-recommends \
  -o "Dir::State::status=${APT_STATUS}" \
  -o "Dir::Cache::archives=${BUNDLE_ROOT}/debian" \
  install "${APT_ROOTS[@]}"
rm -rf "${BUNDLE_ROOT}/debian/partial"
rm -f "${BUNDLE_ROOT}/debian/lock"

if ! find "${BUNDLE_ROOT}/debian" -maxdepth 1 -type f -name '*.deb' \
  -print -quit | grep -q .; then
  printf '%s\n' "FAIL dependency_bundle_apt_candidate" >&2
  exit 1
fi
while IFS= read -r -d '' package; do
  dpkg-deb --field "${package}" Package
done < <(
  find "${BUNDLE_ROOT}/debian" -maxdepth 1 -type f -name '*.deb' -print0 \
    | LC_ALL=C sort -z
) | LC_ALL=C sort -u > "${BUNDLE_ROOT}/debian/package-names.txt"
while IFS= read -r -d '' package; do
  printf '%s=%s\n' \
    "$(dpkg-deb --field "${package}" Package)" \
    "$(dpkg-deb --field "${package}" Version)"
done < <(
  find "${BUNDLE_ROOT}/debian" -maxdepth 1 -type f -name '*.deb' -print0 \
    | LC_ALL=C sort -z
) | LC_ALL=C sort -u > "${BUNDLE_ROOT}/debian/package-specs.txt"
if [[ \
  "$(wc -l < "${BUNDLE_ROOT}/debian/package-names.txt" | tr -d ' ')" \
    != "$(wc -l < "${BUNDLE_ROOT}/debian/package-specs.txt" | tr -d ' ')" \
]]; then
  printf '%s\n' "FAIL dependency_bundle_apt_package_inventory" >&2
  exit 1
fi
(
  cd "${BUNDLE_ROOT}/debian"
  dpkg-scanpackages --multiversion . /dev/null > Packages
  gzip -n -c Packages > Packages.gz
)
install -m 0755 "${INSTALLER_SCRIPT}" \
  "${BUNDLE_ROOT}/install-debian-closure-linux.sh"

python3 "${CONTRACT_SCRIPT}" create-manifest \
  --bundle-root "${BUNDLE_ROOT}" \
  --repo-root "${REPO_ROOT}" \
  --frontend-root "${FRONTEND_ROOT}" \
  --release-sha "${RELEASE_SHA}" \
  --frontend-sha "${FRONTEND_SHA}"
test -f "${BUNDLE_ROOT}/manifest.json"
test -f "${BUNDLE_ROOT}/SHA256SUMS"
python3 "${CONTRACT_SCRIPT}" validate-bundle \
  --bundle-root "${BUNDLE_ROOT}" \
  --repo-root "${REPO_ROOT}" \
  --frontend-root "${FRONTEND_ROOT}" \
  --release-sha "${RELEASE_SHA}" \
  --frontend-sha "${FRONTEND_SHA}"
unshare -n bash "${VALIDATOR_SCRIPT}" \
  "${BUNDLE_ROOT}" "${REPO_ROOT}" "${FRONTEND_ROOT}" \
  "${RELEASE_SHA}" "${FRONTEND_SHA}"
tar -C "${BUILD_ROOT}" --sort=name --mtime='UTC 1970-01-01' \
  --owner=0 --group=0 --numeric-owner -cf - bundle | gzip -n > "${OUTPUT_ARCHIVE}"
sha256sum "${OUTPUT_ARCHIVE}"
