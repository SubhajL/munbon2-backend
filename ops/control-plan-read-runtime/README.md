# Reproducible control-plan read runtime

This directory replaces the host-only runtime commit `c352fdd6` with a secret-free, repo-relative PM2 lifecycle. It starts Flow, Scheduler, ROS-GIS, and the water-planning BFF on loopback only; applies every owned tracked migration before each service starts; keeps command execution and ROS production dark; and refuses activation unless capacity and a continuous five-minute readiness window pass.

## Preconditions

- Linux host with Node/PM2, CPython 3.11, PostgreSQL/Redis/InfluxDB dependencies, and this exact repository checkout.
- Build one service-local environment per Python service at `<service>/.venv` using only its tracked `requirements.txt`. Do this during provisioning, not in PM2 wrappers. Runtime package installs or host-only version overlays are forbidden.
- Central auth is already running on `127.0.0.1:3005`.
- Set `MUNBON_RUNTIME_ENV_DIR` if the mode-600 environment directory is not `/etc/munbon/control-plan-read-runtime`.

Create four operator-owned files and run `chmod 600` on each. Values below are names only; never commit their contents:

| File | Canonical settings |
| --- | --- |
| `flow.env` | `POSTGRES_URL`, `TIMESCALE_URL`, `REDIS_URL`, `INFLUXDB_URL`, `INFLUXDB_TOKEN`, `INFLUXDB_ORG`, `INFLUXDB_BUCKET` |
| `scheduler.env` | `POSTGRES_URL`, central-auth `REDIS_URL`, `JWT_SECRET_KEY`, `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_CLAIM_POLICY_MODE` |
| `ros.env` | `POSTGRES_URL`, isolated `REDIS_URL`; `REQUIREMENT_SOURCE_POSTGRES_URL` is canonical only when the producer is intentionally enabled, but this read-only runtime unsets it and keeps the producer disabled |
| `bff.env` | `POSTGRES_URL`, isolated `REDIS_URL`, `PLANNING_DEPTH_WRITES_ENABLED=false`, `PLANNING_DEPTH_WRITE_LIMIT=10`, `PLANNING_DEPTH_WRITE_WINDOW_SECONDS=300` |

Encoded database credentials stay encoded in `POSTGRES_URL`; RT-3 decodes them once. Do not create decoded DSN aliases. Each wrapper checks mode 600 before sourcing its trusted operator-owned env file.

## Activation and gates

Run from the repository root:

```bash
export MUNBON_RUNTIME_ENV_DIR=/etc/munbon/control-plan-read-runtime
ops/control-plan-read-runtime/activate.sh
```

Activation fails before PM2 changes when `MemAvailable` is below 512 MiB or used swap is above 1 GiB. It starts or updates exactly four processes and immediately snapshots the resulting restart counters. A bounded two-minute startup phase allows only transient missing/offline/not-ready states while migrations and connection pools initialize; capacity faults and restart-counter changes fail immediately. The required five-minute window begins only after the first fully ready sample, then checks capacity, online state, unchanged counters, and exact `status: ready` responses every five seconds. The initial PM2 load is intentional; any later counter change is unexpected and fails the gate. Only then does it run `pm2 save`. Any start, readiness, capacity, or restart failure stops the four new runtime processes and does not save the failed state.

Exact bindings are Flow `127.0.0.1:3011`, Scheduler `127.0.0.1:3021`, ROS-GIS `127.0.0.1:3047`, and BFF `127.0.0.1:3022`. Scheduler remains `CONTROL_EXECUTION_MODE=disabled`, readback remains `off`, SCADA/service-token/capability settings are removed, and ROS daily requirement production remains disabled.

The BFF migration runner verifies and applies the ordered tracked manifest,
requiring both `009_crop_registry` and `010_planning_depth_submissions` in
`water_planning.schema_migrations`. Planning-depth writes remain unavailable
unless the backend flag is the exact string `true`; this runtime keeps it
`false`.

The earlier host snapshot had roughly 330 MiB available and 873 MiB used swap. The new gate therefore correctly blocks that memory state until capacity is recovered; swap alone was below the ceiling.

## Bearer proof

Keep provisioned operator credentials only in the calling process environment, then run:

```bash
MUNBON_OPERATOR_EMAIL='operator@example.invalid' \
MUNBON_OPERATOR_PASSWORD='replace-at-runtime' \
MUNBON_EXPECTED_JWT_AUDIENCE='munbon-services' \
python3 ops/control-plan-read-runtime/verify_bearer.py
```

`MUNBON_EXPECTED_JWT_AUDIENCE` is required and must exactly match the non-secret `JWT_AUDIENCE` configured for central auth and Scheduler; `munbon-services` is the current deployment contract. The verifier fails closed instead of guessing a deployment-specific audience. `verify_bearer.py` prints fixed PASS/FAIL codes only. It proves missing and malformed bearer rejection, central login, issuer/audience/type/subject/JTI/operator claims, real Scheduler and BFF v2 list reads, preserved missing-detail 404s, BFF `Cache-Control: no-store`, logout, and rejected refresh-token reuse. It never prints tokens, cookies, passwords, URLs from failures, or response bodies.

## Backout and diagnostics

Stop the exact runtime set without deleting data or reverting migrations:

```bash
pm2 stop flow-monitoring scheduler ros-gis-integration bff-water-planning
```

Inspect only safe state with `python3 ops/control-plan-read-runtime/runtime_gate.py capacity` and `pm2 status`. Do not print `pm2 jlist`, process environments, env files, or DSNs into tickets/logs. Migrations are forward-only operationally; use an audited database restore or a new forward migration rather than ad hoc down-migration after evidence exists.
