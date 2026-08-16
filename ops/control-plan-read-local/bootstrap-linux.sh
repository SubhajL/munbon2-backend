#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" != "0" || "$#" != "7" ]]; then
  echo "FAIL bootstrap_arguments" >&2
  exit 2
fi

cd /

source /opt/munbon/input/bootstrap-provisioning-state.sh

BOOTSTRAP_PHASE=arguments
BOOTSTRAP_SUBSTEP=validate-arguments
INFLUX_KEY=
NODE_TEMP=
OWNER_TEMP=
STATE_ROOT=/var/lib/munbon-local-acceptance
PROVISION_ROOT="${STATE_ROOT}/provisioning"
BOOTSTRAP_LOG=/run/munbon-bootstrap.log
on_exit() {
  local status=$?
  [[ -z "${INFLUX_KEY}" ]] || rm -f "${INFLUX_KEY}"
  [[ -z "${NODE_TEMP}" ]] || rm -rf "${NODE_TEMP}"
  [[ -z "${OWNER_TEMP}" ]] || rm -f "${OWNER_TEMP}"
  if [[ "${status}" != "0" ]]; then
    local was_interrupted=false
    if [[ "${status}" == "130" || "${status}" == "143" ]]; then
      was_interrupted=true
    fi
    write_bootstrap_failure \
      "${PROVISION_ROOT}" \
      "${RELEASE_SHA:-0000000000000000000000000000000000000000}" \
      "${FRONTEND_SHA:-0000000000000000000000000000000000000000}" \
      "${DEPENDENCY_ARCHIVE_SHA256:-0000000000000000000000000000000000000000000000000000000000000000}" \
      "${BOOTSTRAP_PHASE}" "${BOOTSTRAP_SUBSTEP}" "${status}" \
      "${was_interrupted}" "${BOOTSTRAP_LOG}" /usr/bin/python3 \
      /opt/munbon/input/provisioning_contract.py "${NODE_ROOT:-/usr}" \
      >/dev/null 2>&1 || true
    echo "FAIL bootstrap_${BOOTSTRAP_PHASE}" >&2
  fi
  exit "${status}"
}
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

EXECUTION_KIND="$7"
case "${EXECUTION_KIND}" in
  canonical)
    MACHINE_NAME=munbon-control-plan-local
    ;;
  rehearsal)
    MACHINE_NAME=munbon-control-plan-rehearsal
    ;;
  *)
    echo "FAIL bootstrap_execution_kind" >&2
    exit 2
    ;;
esac
phase() {
  BOOTSTRAP_PHASE="$1"
  echo "${BOOTSTRAP_PHASE}" > /run/munbon-bootstrap-phase
}
substep() {
  BOOTSTRAP_SUBSTEP="$1"
}

SOURCE_BUNDLE="$1"
RELEASE_SHA="$2"
FRONTEND_BUNDLE="$3"
FRONTEND_SHA="$4"
DEPENDENCY_ARCHIVE="$5"
DEPENDENCY_ARCHIVE_SHA256="$6"
INPUT_DIR="$(cd -- "$(dirname -- "${SOURCE_BUNDLE}")" && pwd)"
REPO_ROOT=/opt/munbon/repo
FRONTEND_ROOT=/opt/munbon/frontend
HARNESS_ROOT=/opt/munbon/harness
BROWSER_ROOT=/opt/munbon/browser
PLAYWRIGHT_BROWSERS_PATH=/opt/munbon/playwright-browsers
RUNTIME_ENV_DIR=/etc/munbon/control-plan-read-runtime
EVIDENCE_ROOT="${STATE_ROOT}/evidence"
EVIDENCE_ARCHIVE_ROOT="${STATE_ROOT}/evidence-archive"
NODE_VERSION=22.23.1
NODE_ROOT="/opt/node-v${NODE_VERSION}-linux-arm64"
DEPENDENCY_ROOT=/opt/munbon/dependencies

if [[ \
  "$(uname -m)" != "aarch64" \
  || ! "${RELEASE_SHA}" =~ ^[0-9a-f]{40}$ \
  || ! "${FRONTEND_SHA}" =~ ^[0-9a-f]{40}$ \
  || ! "${DEPENDENCY_ARCHIVE_SHA256}" =~ ^[0-9a-f]{64}$ \
]]; then
  echo "FAIL bootstrap_platform_or_sha" >&2
  exit 1
fi

install -d -m 0700 "${PROVISION_ROOT}"
if [[ -e "${PROVISION_ROOT}/state.json" ]]; then
  echo "FAIL bootstrap_existing_provision_state" >&2
  exit 1
fi
write_bootstrap_state \
  "${PROVISION_ROOT}" created "${RELEASE_SHA}" "${FRONTEND_SHA}" \
  "${DEPENDENCY_ARCHIVE_SHA256}" bootstrap arguments
: > "${BOOTSTRAP_LOG}"
chmod 600 "${BOOTSTRAP_LOG}"
exec > >(tee -a "${BOOTSTRAP_LOG}") 2>&1

phase dependency_archive
substep outer-checksum
if [[ "$(sha256sum "${DEPENDENCY_ARCHIVE}" | awk '{print $1}')" != "${DEPENDENCY_ARCHIVE_SHA256}" ]]; then
  echo "FAIL dependency_archive_checksum" >&2
  exit 1
fi
rm -rf "${DEPENDENCY_ROOT}"
install -d -m 0755 "${DEPENDENCY_ROOT}"
tar -xzf "${DEPENDENCY_ARCHIVE}" --strip-components=1 --directory="${DEPENDENCY_ROOT}"
substep inner-checksum
(
  cd "${DEPENDENCY_ROOT}"
  sha256sum --check --strict SHA256SUMS
)

phase base_packages
substep offline-debian-packages
export DEBIAN_FRONTEND=noninteractive
bash "${DEPENDENCY_ROOT}/install-debian-closure-linux.sh" --install "${DEPENDENCY_ROOT}/debian"
systemctl disable --now prometheus prometheus-node-exporter >/dev/null 2>&1 || true

phase node_runtime
substep node-archive
NODE_ARCHIVE="node-v${NODE_VERSION}-linux-arm64.tar.xz"
install -d -m 0755 "${NODE_ROOT}"
tar -xJf "${DEPENDENCY_ROOT}/${NODE_ARCHIVE}" \
  --strip-components=1 --directory="${NODE_ROOT}"
if [[ \
  "$("${NODE_ROOT}/bin/node" --version)" != "v${NODE_VERSION}" \
  || "$(env PATH="${NODE_ROOT}/bin:/usr/bin:/bin" \
    "${NODE_ROOT}/bin/npm" --version)" != "10.9.8" \
]]; then
  echo "FAIL node_runtime_version" >&2
  exit 1
fi

phase filesystem
if ! id munbon >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash munbon
fi
install -d -o munbon -g munbon -m 0750 \
  /opt/munbon "${HARNESS_ROOT}" "${STATE_ROOT}" "${BROWSER_ROOT}" \
  "${EVIDENCE_ARCHIVE_ROOT}"
install -d -o munbon -g munbon -m 0700 "${RUNTIME_ENV_DIR}"
install -o munbon -g munbon -m 0644 "${SOURCE_BUNDLE}" /opt/munbon/source.bundle
install -o munbon -g munbon -m 0644 \
  "${FRONTEND_BUNDLE}" /opt/munbon/frontend.bundle
for artifact in \
  run-stage-suite.py \
  local-ac1.py \
  seed-approved-sources.py \
  run-ros-manual-producer.sh \
  run-read-browser.js \
  run-evidence-browser.js \
  run-go-read-browser.js \
  run-write-browser.js \
  seed-local-operators.js \
  provisioning_contract.py \
  validate-dependency-bundle-linux.sh \
  verify_bearer.py; do
  install -o munbon -g munbon -m 0750 "${INPUT_DIR}/${artifact}" "${HARNESS_ROOT}/${artifact}"
done
phase source_checkout
if [[ ! -d "${REPO_ROOT}/.git" ]]; then
  runuser -u munbon -- git clone --quiet /opt/munbon/source.bundle "${REPO_ROOT}"
else
  runuser -u munbon -- git -C "${REPO_ROOT}" fetch --quiet --force \
    /opt/munbon/source.bundle refs/heads/main
fi
runuser -u munbon -- git -C "${REPO_ROOT}" checkout --force --quiet \
  --detach "${RELEASE_SHA}"
if [[ "$(runuser -u munbon -- git -C "${REPO_ROOT}" rev-parse HEAD)" != "${RELEASE_SHA}" ]]; then
  echo "FAIL checkout_sha" >&2
  exit 1
fi
if [[ ! -d "${FRONTEND_ROOT}/.git" ]]; then
  runuser -u munbon -- git clone --quiet \
    /opt/munbon/frontend.bundle "${FRONTEND_ROOT}"
else
  runuser -u munbon -- git -C "${FRONTEND_ROOT}" fetch --quiet --force \
    /opt/munbon/frontend.bundle refs/heads/main
fi
runuser -u munbon -- git -C "${FRONTEND_ROOT}" checkout --force --quiet \
  --detach "${FRONTEND_SHA}"
if [[ "$(runuser -u munbon -- git -C "${FRONTEND_ROOT}" rev-parse HEAD)" != "${FRONTEND_SHA}" ]]; then
  echo "FAIL frontend_checkout_sha" >&2
  exit 1
fi

phase dependency_validation
substep content-manifest
python3 "${HARNESS_ROOT}/provisioning_contract.py" validate-bundle \
  --bundle-root "${DEPENDENCY_ROOT}" \
  --repo-root "${REPO_ROOT}" \
  --frontend-root "${FRONTEND_ROOT}" \
  --release-sha "${RELEASE_SHA}" \
  --frontend-sha "${FRONTEND_SHA}"

phase service_manifests
for service in flow-monitoring scheduler ros-gis-integration bff-water-planning; do
  substep "${service}-pip"
  SERVICE_ROOT="${REPO_ROOT}/services/${service}"
  runuser -u munbon -- python3 -m venv "${SERVICE_ROOT}/.venv"
  runuser -u munbon -- "${SERVICE_ROOT}/.venv/bin/pip" install \
    --disable-pip-version-check --quiet --no-index \
    --find-links "${DEPENDENCY_ROOT}/python/${service}" \
    --requirement "${SERVICE_ROOT}/requirements.txt"
  runuser -u munbon -- "${SERVICE_ROOT}/.venv/bin/python" -m pip check >/dev/null
done
ln -sfn .venv "${REPO_ROOT}/services/flow-monitoring/venv"
ln -sfn .venv "${REPO_ROOT}/services/scheduler/venv"
chown -h munbon:munbon "${REPO_ROOT}/services/flow-monitoring/venv" \
  "${REPO_ROOT}/services/scheduler/venv"

install_node_modules() {
  local name="$1"
  local root="$2"
  rm -rf "${root}/node_modules"
  python3 "${HARNESS_ROOT}/provisioning_contract.py" validate-node-archive \
    --name "${name}" \
    --archive "${DEPENDENCY_ROOT}/node-modules/${name}.tar.gz"
  tar -xzf "${DEPENDENCY_ROOT}/node-modules/${name}.tar.gz" \
    --directory "${root}"
  chown -R munbon:munbon "${root}/node_modules"
}

substep auth-node-modules
install_node_modules auth "${REPO_ROOT}/services/auth"
substep pm2-infra-node-modules
install_node_modules pm2 "${REPO_ROOT}/infra/pm2"
substep scada-node-modules
install_node_modules scada "${REPO_ROOT}/services/scada-gate-control"
substep gate-web-node-modules
install_node_modules gate-web "${REPO_ROOT}/services/scada-gate-control-web"
substep frontend-node-modules
install_node_modules frontend "${FRONTEND_ROOT}"
substep dependency-roots-node-modules
cp "${REPO_ROOT}/ops/control-plan-read-local/dependency-roots/package.json" \
  "${BROWSER_ROOT}/package.json"
cp "${REPO_ROOT}/ops/control-plan-read-local/dependency-roots/package-lock.json" \
  "${BROWSER_ROOT}/package-lock.json"
chown munbon:munbon "${BROWSER_ROOT}/package.json" "${BROWSER_ROOT}/package-lock.json"
install_node_modules dependency-roots "${BROWSER_ROOT}"
rm -rf "${PLAYWRIGHT_BROWSERS_PATH}"
cp -a "${DEPENDENCY_ROOT}/playwright-browsers" "${PLAYWRIGHT_BROWSERS_PATH}"
chown -R munbon:munbon "${BROWSER_ROOT}" "${PLAYWRIGHT_BROWSERS_PATH}"

phase dependency_staged
substep state-transition
python3 "${HARNESS_ROOT}/provisioning_contract.py" state \
  --state-root "${PROVISION_ROOT}" \
  --state dependency-staged \
  --release-sha "${RELEASE_SHA}" \
  --frontend-sha "${FRONTEND_SHA}" \
  --dependency-sha256 "${DEPENDENCY_ARCHIVE_SHA256}" \
  --phase dependency-staged \
  --substep complete

phase evidence_archive
substep archive-prior-evidence
if [[ \
  -d "${EVIDENCE_ROOT}" \
  && -n "$(find "${EVIDENCE_ROOT}" -mindepth 1 -maxdepth 1 -print -quit)" \
]]; then
  PREVIOUS_RELEASE=unknown
  if [[ -f "${STATE_ROOT}/owner.json" ]]; then
    CANDIDATE_RELEASE="$(jq -r '.release_sha // empty' "${STATE_ROOT}/owner.json")"
    if [[ "${CANDIDATE_RELEASE}" =~ ^[0-9a-f]{40}$ ]]; then
      PREVIOUS_RELEASE="${CANDIDATE_RELEASE}"
    fi
  fi
  ARCHIVE_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
  mv -- "${EVIDENCE_ROOT}" \
    "${EVIDENCE_ARCHIVE_ROOT}/${PREVIOUS_RELEASE}-${ARCHIVE_STAMP}-$$"
fi
install -d -o munbon -g munbon -m 0700 "${EVIDENCE_ROOT}"

phase runtime_quiesce
substep stop-runtime
systemctl stop munbon-local-auth >/dev/null 2>&1 || true
runuser -u munbon -- env PATH="${NODE_ROOT}/bin:/usr/bin:/bin" \
  "${NODE_ROOT}/bin/node" "${BROWSER_ROOT}/node_modules/pm2/bin/pm2" \
  delete all >/dev/null 2>&1 || true

phase secrets
SECRETS_FILE="${RUNTIME_ENV_DIR}/local-secrets.env"
if [[ ! -f "${SECRETS_FILE}" ]]; then
  umask 077
  DB_PASSWORD="$(openssl rand -hex 24)"
  JWT_SECRET="$(openssl rand -hex 48)"
  SESSION_SECRET="$(openssl rand -hex 32)"
  INFLUX_TOKEN="$(openssl rand -hex 48)"
  OPERATOR_PASSWORD="L1!$(openssl rand -hex 20)aA"
  FIELD_TEAM_PASSWORD="L1!$(openssl rand -hex 20)aA"
  DAILY_REQUIREMENT_MANUAL_TOKEN="$(openssl rand -hex 48)"
  {
    echo "DB_PASSWORD=${DB_PASSWORD}"
    echo "JWT_SECRET=${JWT_SECRET}"
    echo "SESSION_SECRET=${SESSION_SECRET}"
    echo "INFLUX_TOKEN=${INFLUX_TOKEN}"
    echo "OPERATOR_PASSWORD=${OPERATOR_PASSWORD}"
    echo "FIELD_TEAM_PASSWORD=${FIELD_TEAM_PASSWORD}"
    echo "DAILY_REQUIREMENT_MANUAL_TOKEN=${DAILY_REQUIREMENT_MANUAL_TOKEN}"
  } > "${SECRETS_FILE}"
fi
if ! grep -q '^DAILY_REQUIREMENT_MANUAL_TOKEN=' "${SECRETS_FILE}"; then
  DAILY_REQUIREMENT_MANUAL_TOKEN="$(openssl rand -hex 48)"
  echo "DAILY_REQUIREMENT_MANUAL_TOKEN=${DAILY_REQUIREMENT_MANUAL_TOKEN}" \
    >> "${SECRETS_FILE}"
fi
# Backfill for guests provisioned before the field-team drill existed.
if ! grep -q '^FIELD_TEAM_PASSWORD=' "${SECRETS_FILE}"; then
  FIELD_TEAM_PASSWORD="L1!$(openssl rand -hex 20)aA"
  echo "FIELD_TEAM_PASSWORD=${FIELD_TEAM_PASSWORD}" >> "${SECRETS_FILE}"
fi
chown munbon:munbon "${SECRETS_FILE}"
chmod 600 "${SECRETS_FILE}"
set -a
source "${SECRETS_FILE}"
set +a

phase postgres_redis
systemctl enable --now postgresql redis-server >/dev/null
runuser -u postgres -- psql --set=ON_ERROR_STOP=1 -Atqc \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='munbon_local' AND pid <> pg_backend_pid()" \
  >/dev/null
runuser -u postgres -- dropdb --if-exists munbon_local
if ! runuser -u postgres -- psql -Atqc "SELECT 1 FROM pg_roles WHERE rolname='munbon_local'" \
  | grep -qx 1; then
  runuser -u postgres -- createuser --no-superuser --no-createdb --no-createrole munbon_local
fi
substep postgres-role
runuser -u postgres -- psql --set=ON_ERROR_STOP=1 \
  --set=database_password="${DB_PASSWORD}" <<'SQL' >/dev/null
ALTER ROLE munbon_local PASSWORD :'database_password';
SQL
if ! runuser -u postgres -- psql -Atqc "SELECT 1 FROM pg_database WHERE datname='munbon_local'" \
  | grep -qx 1; then
  runuser -u postgres -- createdb --owner=munbon_local munbon_local
fi
substep postgis-extension
runuser -u postgres -- psql --set=ON_ERROR_STOP=1 \
  --dbname=munbon_local <<'SQL' >/dev/null
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS auth AUTHORIZATION munbon_local;
ALTER SCHEMA auth OWNER TO munbon_local;
SQL

sed -ri 's/^bind .*/bind 127.0.0.1 ::1/' /etc/redis/redis.conf
systemctl restart redis-server
redis-cli FLUSHALL >/dev/null
phase influx_runtime
install -d -m 0755 /etc/systemd/system/influxdb.service.d
cat > /etc/systemd/system/influxdb.service.d/loopback.conf <<'EOF'
[Service]
Type=simple
PIDFile=
TimeoutStartSec=120
ExecStart=
ExecStart=/usr/bin/influxd --http-bind-address=127.0.0.1:8086
EOF
systemctl daemon-reload
systemctl reset-failed influxdb >/dev/null 2>&1 || true
systemctl enable influxdb >/dev/null
systemctl restart influxdb
for _attempt in $(seq 1 60); do
  curl --fail --silent http://127.0.0.1:8086/health >/dev/null && break
  sleep 1
done
if ! curl --fail --silent http://127.0.0.1:8086/health >/dev/null; then
  echo "FAIL influx_readiness" >&2
  exit 1
fi
if curl --fail --silent http://127.0.0.1:8086/api/v2/setup | jq -e '.allowed == true' >/dev/null; then
  SETUP_PAYLOAD="$(mktemp)"
  chmod 600 "${SETUP_PAYLOAD}"
  jq -n \
    --arg username munbon-local \
    --arg password "${OPERATOR_PASSWORD}" \
    --arg token "${INFLUX_TOKEN}" \
    --arg org munbon \
    --arg bucket flow_monitoring \
    '{username:$username,password:$password,token:$token,org:$org,bucket:$bucket}' \
    > "${SETUP_PAYLOAD}"
  curl --fail --silent --request POST --header 'Content-Type: application/json' \
    --data-binary "@${SETUP_PAYLOAD}" http://127.0.0.1:8086/api/v2/setup >/dev/null
  rm -f "${SETUP_PAYLOAD}"
fi

phase runtime_environment
POSTGRES_URL_VALUE="postgresql://munbon_local:${DB_PASSWORD}@127.0.0.1:5432/munbon_local"
cat > "${RUNTIME_ENV_DIR}/flow.env" <<EOF
POSTGRES_URL=${POSTGRES_URL_VALUE}
TIMESCALE_URL=${POSTGRES_URL_VALUE}
REDIS_URL=redis://127.0.0.1:6379/3
INFLUXDB_URL=http://127.0.0.1:8086
INFLUXDB_TOKEN=${INFLUX_TOKEN}
INFLUXDB_ORG=munbon
INFLUXDB_BUCKET=flow_monitoring
EOF
cat > "${RUNTIME_ENV_DIR}/scheduler.env" <<EOF
POSTGRES_URL=${POSTGRES_URL_VALUE}
REDIS_URL=redis://127.0.0.1:6379/4
JWT_SECRET_KEY=${JWT_SECRET}
JWT_ISSUER=munbon-auth
JWT_AUDIENCE=munbon-services
JWT_CLAIM_POLICY_MODE=strict
EOF
cat > "${RUNTIME_ENV_DIR}/ros.env" <<EOF
POSTGRES_URL=${POSTGRES_URL_VALUE}
REDIS_URL=redis://127.0.0.1:6379/5
EOF
cat > "${RUNTIME_ENV_DIR}/bff.env" <<EOF
POSTGRES_URL=${POSTGRES_URL_VALUE}
REDIS_URL=redis://127.0.0.1:6379/2
PLANNING_DEPTH_WRITES_ENABLED=false
EOF
cat > "${RUNTIME_ENV_DIR}/auth.env" <<EOF
NODE_ENV=development
HOST=127.0.0.1
PORT=3005
DATABASE_URL=${POSTGRES_URL_VALUE}
DATABASE_SSL=false
REDIS_URL=redis://127.0.0.1:6379/1
JWT_SECRET=${JWT_SECRET}
JWT_ISSUER=munbon-auth
JWT_AUDIENCE=munbon-services
SESSION_SECRET=${SESSION_SECRET}
OAUTH_CALLBACK_URL=http://127.0.0.1:3005/api/v1/oauth/callback
THAI_DIGITAL_ID_CLIENT_ID=local-disabled
THAI_DIGITAL_ID_CLIENT_SECRET=local-disabled
THAI_DIGITAL_ID_AUTH_URL=http://127.0.0.1:9/disabled
THAI_DIGITAL_ID_TOKEN_URL=http://127.0.0.1:9/disabled
THAI_DIGITAL_ID_USERINFO_URL=http://127.0.0.1:9/disabled
SMTP_HOST=127.0.0.1
SMTP_PORT=9
SMTP_USER=local-disabled
SMTP_PASS=local-disabled
EMAIL_FROM=local@example.invalid
CORS_ORIGIN=http://127.0.0.1:9999
LOG_LEVEL=error
EOF
cat > "${RUNTIME_ENV_DIR}/operator.env" <<EOF
MUNBON_OPERATOR_EMAIL=operator@example.com
MUNBON_OPERATOR_PASSWORD=${OPERATOR_PASSWORD}
MUNBON_EXPECTED_JWT_AUDIENCE=munbon-services
MUNBON_EXPECTED_JWT_ISSUER=munbon-auth
MUNBON_EXPECTED_ROLE=operator
EOF
# A separate, disposable non-operator principal. LOCAL-WRITE-UI-1 uses it to
# prove planning-depth is DENIED (roster/active 403, Submit not rendered), so it
# must never be granted operator rights.
cat > "${RUNTIME_ENV_DIR}/field-team.env" <<EOF
MUNBON_FIELD_TEAM_EMAIL=field-team@example.com
MUNBON_FIELD_TEAM_PASSWORD=${FIELD_TEAM_PASSWORD}
EOF
chown munbon:munbon "${RUNTIME_ENV_DIR}"/*.env
chmod 600 "${RUNTIME_ENV_DIR}"/*.env

phase runtime_reset
substep state-transition
python3 "${HARNESS_ROOT}/provisioning_contract.py" state \
  --state-root "${PROVISION_ROOT}" \
  --state runtime-reset \
  --release-sha "${RELEASE_SHA}" \
  --frontend-sha "${FRONTEND_SHA}" \
  --dependency-sha256 "${DEPENDENCY_ARCHIVE_SHA256}" \
  --phase runtime-reset \
  --substep complete

phase auth
substep seed-local-operators
runuser -u munbon -- env NODE_ROOT="${NODE_ROOT}" bash -c \
  'set -a; source /etc/munbon/control-plan-read-runtime/auth.env; source /etc/munbon/control-plan-read-runtime/operator.env; source /etc/munbon/control-plan-read-runtime/field-team.env; set +a; export MUNBON_REPO_ROOT=/opt/munbon/repo; "${NODE_ROOT}/bin/node" /opt/munbon/harness/seed-local-operators.js'
install -o root -g root -m 0644 "${INPUT_DIR}/munbon-local-auth.service" \
  /etc/systemd/system/munbon-local-auth.service
systemctl daemon-reload
systemctl enable --now munbon-local-auth >/dev/null
for _attempt in $(seq 1 60); do
  curl --fail --silent http://127.0.0.1:3005/health/ready >/dev/null && break
  sleep 1
done
if ! curl --fail --silent http://127.0.0.1:3005/health/ready >/dev/null; then
  echo "FAIL auth_readiness" >&2
  exit 1
fi

phase monitoring
install -d -m 0755 /etc/prometheus
install -m 0644 "${REPO_ROOT}/infra/monitoring/control-plane-alerts.yml" \
  /etc/prometheus/control-plane-alerts.yml
install -m 0644 "${REPO_ROOT}/infra/monitoring/control-plane-prometheus.yml" \
  /etc/prometheus/control-plane-prometheus.yml
cat > /etc/prometheus/control-plane-central-targets.json <<'EOF'
[{"targets":["127.0.0.1:3021"]}]
EOF
cat > /etc/prometheus/control-plane-field-targets.json <<'EOF'
[{"targets":["127.0.0.1:3030"]}]
EOF
cat > /etc/prometheus/control-plane-readiness-targets.json <<'EOF'
[{"targets":["http://127.0.0.1:3021/ready"]}]
EOF
chmod 0644 \
  /etc/prometheus/control-plane-central-targets.json \
  /etc/prometheus/control-plane-field-targets.json \
  /etc/prometheus/control-plane-readiness-targets.json

phase ownership
substep pm2-daemon
for _attempt in $(seq 1 10); do
  runuser -u munbon -- env PATH="${NODE_ROOT}/bin:/usr/bin:/bin" \
    "${NODE_ROOT}/bin/node" "${BROWSER_ROOT}/node_modules/pm2/bin/pm2" \
    ping >/dev/null 2>&1 && break
  sleep 1
done
if ! runuser -u munbon -- env PATH="${NODE_ROOT}/bin:/usr/bin:/bin" \
  "${NODE_ROOT}/bin/node" "${BROWSER_ROOT}/node_modules/pm2/bin/pm2" \
  ping >/dev/null 2>&1; then
  echo "FAIL pm2_daemon" >&2
  exit 1
fi
substep ready-state
python3 "${HARNESS_ROOT}/provisioning_contract.py" state \
  --state-root "${PROVISION_ROOT}" \
  --state ready \
  --release-sha "${RELEASE_SHA}" \
  --frontend-sha "${FRONTEND_SHA}" \
  --dependency-sha256 "${DEPENDENCY_ARCHIVE_SHA256}" \
  --phase ownership \
  --substep ready-state
phase complete
substep owner-marker
OWNER_TEMP="${STATE_ROOT}/.owner.json.$$"
if [[ "${EXECUTION_KIND}" == "rehearsal" ]]; then
  cat > "${OWNER_TEMP}" <<EOF
{"machine":"${MACHINE_NAME}","architecture":"arm64","state":"ready","release_sha":"${RELEASE_SHA}","frontend_sha":"${FRONTEND_SHA}","dependency_sha256":"${DEPENDENCY_ARCHIVE_SHA256}","execution_kind":"rehearsal","acceptance_evidence":false}
EOF
else
  cat > "${OWNER_TEMP}" <<EOF
{"machine":"${MACHINE_NAME}","architecture":"arm64","state":"ready","release_sha":"${RELEASE_SHA}","frontend_sha":"${FRONTEND_SHA}","dependency_sha256":"${DEPENDENCY_ARCHIVE_SHA256}"}
EOF
fi
chown munbon:munbon "${OWNER_TEMP}"
chmod 600 "${OWNER_TEMP}"
mv -- "${OWNER_TEMP}" "${STATE_ROOT}/owner.json"
OWNER_TEMP=
echo "PASS bootstrap_linux"
