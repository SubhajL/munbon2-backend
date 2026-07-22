# PM2 control-plane infrastructure

This package builds two explicit host topologies:

- `ecosystem-irrigation.config.js`: the central irrigation host, including Flow, Scheduler, and the bounded `scheduler-control-dispatch` tick.
- `ecosystem-scada-field.config.js`: the field-capable host, containing only `scada-gate-control`. It is not the legacy `scada-service`.

Both tracked command gates are dark: Scheduler uses `CONTROL_EXECUTION_MODE=disabled`; SCADA uses `ALLOW_MACHINE_COMMANDS=false`. Trust-artifact and service-auth variables are passed through only when the host supplies them.

## Build and verify

```bash
npm ci
npm run lint
npm run verify
npm run build
```

`npm run verify` runs the typecheck and Jest suites for topology, exact-release preflight, monitoring coverage, and evidence redaction.

## Deployment gates

Do not call PM2 until the role-specific preflight exits successfully:

```bash
npm run preflight -- --role central --expected-commit "$CONTROL_RELEASE_SHA"
npm run preflight -- --role field --expected-commit "$CONTROL_RELEASE_SHA"
```

The central preflight reads Scheduler migration IDs and full checksums through a read-only `psql` session using `POSTGRES_URL`. Both roles verify the exact Git commit, a clean tracked tree, required built entry points, the correct PM2 process boundary, and dark command gates. The report never includes process environments or credentials.

The complete ordering, environment requirements, monitoring installation, safe evidence commands, and rollback boundary are in [CONTROL_PLANE_DARK_DEPLOYMENT.md](../../docs/operations/CONTROL_PLANE_DARK_DEPLOYMENT.md).
