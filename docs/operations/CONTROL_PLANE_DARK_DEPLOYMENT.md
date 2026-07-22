# Control-plane dark deployment and evidence runbook

This runbook deploys software only. It does not authorize commandability, issue authority, call a machine execution endpoint, or send a Modbus request. Keep `CONTROL_EXECUTION_MODE=disabled` and `ALLOW_MACHINE_COMMANDS=false` throughout this procedure.

## Release inputs

Record the approved full 40-character commit as `CONTROL_RELEASE_SHA`. Build from an immutable checkout of that commit. The central host requires its existing PM2 credentials plus `POSTGRES_URL`; the field host requires `DATABASE_URL`, `JWT_SECRET`, and `MODBUS_HOST`. Do not place values in shell history, manifests, or evidence output.

Trust inputs remain optional while dark:

- Flow: `HYDRAULIC_COMMANDABILITY_APPROVAL_PATH`
- Scheduler: `SCHEDULER_SCADA_BASE_URL` and the `SCHEDULER_SERVICE_JWT_*` variables
- SCADA: `SCADA_APPROVED_FIELD_BUNDLE_PATH`, `SCADA_SITE_CANONICAL_GATE_ID`, and the `SCHEDULER_SERVICE_JWT_*` variables

Supplying trust inputs does not change either tracked command gate. A later trust cutover requires its own operational approval and receipt-store rotation.

## Build and preflight before PM2 replacement

On the central host:

```bash
npm --prefix infra/pm2 ci
npm --prefix infra/pm2 run lint
npm --prefix infra/pm2 run verify
npm --prefix infra/pm2 run build
npm --prefix infra/pm2 run preflight -- --role central --expected-commit "$CONTROL_RELEASE_SHA"
```

The central preflight fails unless the checkout exactly matches `CONTROL_RELEASE_SHA`, tracked files are clean, migration `0013_operator_approved_execution` and every other tracked migration have exact applied checksums, required entry points exist, and Scheduler plus the one-minute bounded worker remain dark.

Only after a successful preflight:

```bash
pm2 startOrReload infra/pm2/ecosystem-irrigation.config.js --only flow-monitoring,scheduler,scheduler-control-dispatch --update-env
```

On the chosen field-capable host:

```bash
npm --prefix services/scada-gate-control ci
npm --prefix services/scada-gate-control run typecheck
npm --prefix services/scada-gate-control run lint
npm --prefix services/scada-gate-control test
npm --prefix services/scada-gate-control run build
npm --prefix infra/pm2 ci
npm --prefix infra/pm2 run build
npm --prefix infra/pm2 run preflight -- --role field --expected-commit "$CONTROL_RELEASE_SHA"
pm2 startOrReload infra/pm2/ecosystem-scada-field.config.js --only scada-gate-control --update-env
```

The field preflight refuses the legacy `scada-service`, missing binaries, or an armed machine flag.

## Monitoring

Install `infra/monitoring/control-plane-prometheus.yml` and `control-plane-alerts.yml` in Prometheus, plus a blackbox exporter using an `http_2xx` module. Copy each `*.example.json` target file to the corresponding non-example filename and replace every `.example.invalid` target with the SRE-approved internal address before reload. Never deploy the example targets.

The rules cover Scheduler and SCADA readiness, worker heartbeat, Scheduler scrape errors, a stale binary missing current execution metrics, validation rejections, readback mismatches, in-doubt outcomes, and any physical write attributed to shadow mode. Validate and reload with the site's standard `promtool` and Prometheus procedure; alert receiver delivery requires a separate drill.

## Read-only evidence

The collector calls only Git, `pm2 jlist`, read-only Postgres queries, `/ready` or `/health`, and `/metrics`. It never prints PM2 environments, database errors, response debug fields, or non-allowlisted metric series. HTTP responses, artifacts, and metric output are capped.

Central host example:

```bash
npm --prefix infra/pm2 run collect-evidence -- \
  --role central \
  --expected-commit "$CONTROL_RELEASE_SHA" \
  --scheduler-url http://127.0.0.1:3021 \
  --release-file /secure/evidence/model-snapshot-v4.json \
  --artifact /secure/approvals/commandability.json \
  > control-plane-central-evidence.json
```

Field host example:

```bash
npm --prefix infra/pm2 run collect-evidence -- \
  --role field \
  --expected-commit "$CONTROL_RELEASE_SHA" \
  --scada-url http://127.0.0.1:3030 \
  --artifact /secure/approvals/d6-field-bundle.json \
  > control-plane-field-evidence.json
```

Central evidence includes exact migration IDs/checksums and counts for plan runs, grants, grant events, and complete drill evidence sets. Release identity is selected from the supplied snapshot; artifact contents are never emitted, only filenames and SHA-256 hashes. An unavailable probe is listed by name and never represented as healthy.

## Acceptance and backout

Accept a dark deployment only when both preflights approve the same commit, PM2 reports the intended process names online, Scheduler readiness reports migrations/tables/Redis healthy, SCADA health and both metrics endpoints respond, the worker heartbeat is fresh, and all tracked command gates remain dark. Archive the two safe JSON reports with the release manifest.

Backout is process-scoped: restore the previous immutable release and rerun that release's preflight before `startOrReload`. Do not roll back migration `0013` while any code that requires it is running. A failed preflight or unavailable evidence probe means stop; it never authorizes continuing from a partial green signal.
