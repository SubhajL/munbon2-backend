#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" != "0" || "$#" != "4" ]]; then
  echo "FAIL bootstrap_arguments" >&2
  exit 2
fi

cd /

BOOTSTRAP_PHASE=arguments
INFLUX_KEY=
NODE_TEMP=
on_exit() {
  local status=$?
  [[ -z "${INFLUX_KEY}" ]] || rm -f "${INFLUX_KEY}"
  [[ -z "${NODE_TEMP}" ]] || rm -rf "${NODE_TEMP}"
  if [[ "${status}" != "0" ]]; then
    echo "FAIL bootstrap_${BOOTSTRAP_PHASE}" >&2
  fi
  exit "${status}"
}
trap on_exit EXIT
phase() {
  BOOTSTRAP_PHASE="$1"
  echo "${BOOTSTRAP_PHASE}" > /run/munbon-bootstrap-phase
}

SOURCE_BUNDLE="$1"
RELEASE_SHA="$2"
FRONTEND_BUNDLE="$3"
FRONTEND_SHA="$4"
INPUT_DIR="$(cd -- "$(dirname -- "${SOURCE_BUNDLE}")" && pwd)"
REPO_ROOT=/opt/munbon/repo
FRONTEND_ROOT=/opt/munbon/frontend
HARNESS_ROOT=/opt/munbon/harness
BROWSER_ROOT=/opt/munbon/browser
PLAYWRIGHT_BROWSERS_PATH=/opt/munbon/playwright-browsers
RUNTIME_ENV_DIR=/etc/munbon/control-plan-read-runtime
STATE_ROOT=/var/lib/munbon-local-acceptance
EVIDENCE_ROOT="${STATE_ROOT}/evidence"
EVIDENCE_ARCHIVE_ROOT="${STATE_ROOT}/evidence-archive"
INFLUX_FINGERPRINT=24C975CBA61A024EE1B631787C3D57159FC2F927
PM2_VERSION=5.4.3
NODE_VERSION=22.23.1
NODE_ROOT="/opt/node-v${NODE_VERSION}-linux-arm64"

if [[ \
  "$(uname -m)" != "aarch64" \
  || ! "${RELEASE_SHA}" =~ ^[0-9a-f]{40}$ \
  || ! "${FRONTEND_SHA}" =~ ^[0-9a-f]{40}$ \
]]; then
  echo "FAIL bootstrap_platform_or_sha" >&2
  exit 1
fi

phase base_packages
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
  build-essential ca-certificates coinor-cbc curl gdal-bin git gnupg jq \
  libgdal-dev libgeos-dev \
  libpq-dev nodejs npm openssl \
  postgresql postgresql-contrib postgis prometheus python3 python3-dev python3-venv \
  redis-server rsync xz-utils
systemctl disable --now prometheus prometheus-node-exporter >/dev/null 2>&1 || true

phase node_runtime
NODE_TEMP="$(mktemp -d)"
NODE_ARCHIVE="node-v${NODE_VERSION}-linux-arm64.tar.xz"
curl --fail --silent --show-error --location \
  "https://nodejs.org/dist/v${NODE_VERSION}/${NODE_ARCHIVE}" \
  --output "${NODE_TEMP}/${NODE_ARCHIVE}"
curl --fail --silent --show-error --location \
  "https://nodejs.org/dist/v${NODE_VERSION}/SHASUMS256.txt" \
  --output "${NODE_TEMP}/SHASUMS256.txt"
(
  cd "${NODE_TEMP}"
  grep " ${NODE_ARCHIVE}$" SHASUMS256.txt | sha256sum --check --status
)
install -d -m 0755 "${NODE_ROOT}"
tar -xJf "${NODE_TEMP}/${NODE_ARCHIVE}" \
  --strip-components=1 --directory="${NODE_ROOT}"
if [[ "$("${NODE_ROOT}/bin/node" --version)" != "v${NODE_VERSION}" ]]; then
  echo "FAIL node_runtime_version" >&2
  exit 1
fi

install -d -m 0755 /etc/apt/keyrings
INFLUX_KEY="$(mktemp)"
phase influx_packages
curl --fail --silent --show-error --location \
  https://repos.influxdata.com/influxdata-archive.key --output "${INFLUX_KEY}"
if ! gpg --show-keys --with-fingerprint --with-colons "${INFLUX_KEY}" 2>/dev/null \
  | grep -q "^fpr:::::::::${INFLUX_FINGERPRINT}:$"; then
  echo "FAIL influx_signing_key" >&2
  exit 1
fi
gpg --dearmor --yes --output /etc/apt/keyrings/influxdata-archive.gpg "${INFLUX_KEY}"
echo 'deb [signed-by=/etc/apt/keyrings/influxdata-archive.gpg] https://repos.influxdata.com/debian stable main' \
  > /etc/apt/sources.list.d/influxdata.list
apt-get update -qq
apt-get install -y -qq influxdb2
npm install --global --silent "pm2@${PM2_VERSION}"

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
  seed-local-operators.js \
  verify_bearer.py; do
  install -o munbon -g munbon -m 0750 "${INPUT_DIR}/${artifact}" "${HARNESS_ROOT}/${artifact}"
done

phase evidence_archive
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
systemctl stop munbon-local-auth >/dev/null 2>&1 || true
runuser -u munbon -- pm2 delete all >/dev/null 2>&1 || true

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

phase secrets
SECRETS_FILE="${RUNTIME_ENV_DIR}/local-secrets.env"
if [[ ! -f "${SECRETS_FILE}" ]]; then
  umask 077
  DB_PASSWORD="$(openssl rand -hex 24)"
  JWT_SECRET="$(openssl rand -hex 48)"
  SESSION_SECRET="$(openssl rand -hex 32)"
  INFLUX_TOKEN="$(openssl rand -hex 48)"
  OPERATOR_PASSWORD="L1!$(openssl rand -hex 20)aA"
  DAILY_REQUIREMENT_MANUAL_TOKEN="$(openssl rand -hex 48)"
  {
    echo "DB_PASSWORD=${DB_PASSWORD}"
    echo "JWT_SECRET=${JWT_SECRET}"
    echo "SESSION_SECRET=${SESSION_SECRET}"
    echo "INFLUX_TOKEN=${INFLUX_TOKEN}"
    echo "OPERATOR_PASSWORD=${OPERATOR_PASSWORD}"
    echo "DAILY_REQUIREMENT_MANUAL_TOKEN=${DAILY_REQUIREMENT_MANUAL_TOKEN}"
  } > "${SECRETS_FILE}"
fi
if ! grep -q '^DAILY_REQUIREMENT_MANUAL_TOKEN=' "${SECRETS_FILE}"; then
  DAILY_REQUIREMENT_MANUAL_TOKEN="$(openssl rand -hex 48)"
  echo "DAILY_REQUIREMENT_MANUAL_TOKEN=${DAILY_REQUIREMENT_MANUAL_TOKEN}" \
    >> "${SECRETS_FILE}"
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
runuser -u postgres -- psql --set=database_password="${DB_PASSWORD}" <<'SQL' >/dev/null
ALTER ROLE munbon_local PASSWORD :'database_password';
SQL
if ! runuser -u postgres -- psql -Atqc "SELECT 1 FROM pg_database WHERE datname='munbon_local'" \
  | grep -qx 1; then
  runuser -u postgres -- createdb --owner=munbon_local munbon_local
fi
runuser -u postgres -- psql --dbname=munbon_local <<'SQL' >/dev/null
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
chown munbon:munbon "${RUNTIME_ENV_DIR}"/*.env
chmod 600 "${RUNTIME_ENV_DIR}"/*.env

phase service_manifests
for service in flow-monitoring scheduler ros-gis-integration bff-water-planning; do
  SERVICE_ROOT="${REPO_ROOT}/services/${service}"
  if [[ ! -x "${SERVICE_ROOT}/.venv/bin/python" ]]; then
    runuser -u munbon -- python3 -m venv "${SERVICE_ROOT}/.venv"
  fi
  runuser -u munbon -- "${SERVICE_ROOT}/.venv/bin/pip" install \
    --disable-pip-version-check --quiet --requirement "${SERVICE_ROOT}/requirements.txt"
  runuser -u munbon -- "${SERVICE_ROOT}/.venv/bin/pip" check >/dev/null
done
ln -sfn .venv "${REPO_ROOT}/services/flow-monitoring/venv"
ln -sfn .venv "${REPO_ROOT}/services/scheduler/venv"
chown -h munbon:munbon "${REPO_ROOT}/services/flow-monitoring/venv" \
  "${REPO_ROOT}/services/scheduler/venv"
runuser -u munbon -- npm --prefix "${REPO_ROOT}/services/auth" ci --omit=dev --silent
runuser -u munbon -- npm --prefix "${REPO_ROOT}/infra/pm2" ci --silent
runuser -u munbon -- env \
  PATH="${NODE_ROOT}/bin:/usr/bin:/bin" \
  "${NODE_ROOT}/bin/npm" --prefix \
  "${REPO_ROOT}/services/scada-gate-control" ci --silent
runuser -u munbon -- env \
  PATH="${NODE_ROOT}/bin:/usr/bin:/bin" \
  "${NODE_ROOT}/bin/npm" --prefix \
  "${REPO_ROOT}/services/scada-gate-control-web" ci --silent
runuser -u munbon -- env \
  PATH="${NODE_ROOT}/bin:/usr/bin:/bin" \
  "${NODE_ROOT}/bin/npm" --prefix "${FRONTEND_ROOT}" ci --silent
(
  cd "${FRONTEND_ROOT}"
  runuser -u munbon -- env \
    PATH="${NODE_ROOT}/bin:/usr/bin:/bin" \
    "${NODE_ROOT}/bin/npm" exec prisma generate
)
runuser -u munbon -- env \
  PATH="${NODE_ROOT}/bin:/usr/bin:/bin" \
  "${NODE_ROOT}/bin/npm" --prefix "${BROWSER_ROOT}" install --silent \
  "playwright@1.54.2"
(
  cd "${BROWSER_ROOT}"
  PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH}" \
    PATH="${NODE_ROOT}/bin:/usr/bin:/bin" \
    "${NODE_ROOT}/bin/npx" playwright install --with-deps chromium
)
chown -R munbon:munbon "${BROWSER_ROOT}" "${PLAYWRIGHT_BROWSERS_PATH}"

phase auth
runuser -u munbon -- bash -c \
  'set -a; source /etc/munbon/control-plan-read-runtime/auth.env; source /etc/munbon/control-plan-read-runtime/operator.env; set +a; export MUNBON_REPO_ROOT=/opt/munbon/repo; node /opt/munbon/harness/seed-local-operators.js'
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

phase ownership
for _attempt in $(seq 1 10); do
  runuser -u munbon -- pm2 ping >/dev/null 2>&1 && break
  sleep 1
done
if ! runuser -u munbon -- pm2 ping >/dev/null 2>&1; then
  echo "FAIL pm2_daemon" >&2
  exit 1
fi
cat > "${STATE_ROOT}/owner.json" <<EOF
{"machine":"munbon-control-plan-local","architecture":"arm64","release_sha":"${RELEASE_SHA}"}
EOF
chown munbon:munbon "${STATE_ROOT}/owner.json"
chmod 600 "${STATE_ROOT}/owner.json"
phase complete
echo "PASS bootstrap_linux"
