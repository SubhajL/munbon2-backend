# Control-plan all-stages local acceptance

This runbook enforces the local-first promotion contract. Every roadmap stage
must pass in the isolated local environment, followed by `LOCAL-RC-1`, before
any production promotion work begins. No AWS action, including inventory or
SSH, is part of this runbook.

## Isolation and ownership

- Machine: `munbon-control-plan-local`
- Platform: Debian 12 on native `arm64`
- Resources: 8 GiB memory, 4 CPUs, 40 GiB disk limit
- Isolation: OrbStack filesystem isolation and host/guest network isolation
- Runtime checkout: `/opt/munbon/repo`
- Runtime environment: `/etc/munbon/control-plan-read-runtime`
- Guest evidence: `/var/lib/munbon-local-acceptance/evidence`
- PM2 owner: the guest-local `munbon` user

The existing OrbStack `ubuntu` guest, Mac databases and containers, production
credentials, and AWS hosts are not used. Source enters the guest as an exact Git
bundle; the runtime checkout must remain at the accepted 40-character SHA.

## Promotion sequence

| Roadmap proof      | Local gate                 | Current harness status       |
| ------------------ | -------------------------- | ---------------------------- |
| BASE-0             | `LOCAL-BASE-0`             | Implemented and passed       |
| RTA-1              | `LOCAL-RTA-1`              | Implemented and passed       |
| AC-1               | `LOCAL-AC-1`               | Planned; not yet implemented |
| READ-ACT-1         | `LOCAL-READ-ACT-1`         | Planned; not yet implemented |
| ME-1 / FE-8        | `LOCAL-EVIDENCE-1`         | Planned; not yet implemented |
| W1 / W2            | `LOCAL-WRITE-FOUNDATION-1` | Planned; not yet implemented |
| FE-5 / FE-6        | `LOCAL-WRITE-UI-1`         | Planned; not yet implemented |
| DEC-W4             | `LOCAL-PERSIST-ONLY-1`     | Planned; persist-only        |
| WRITE-ACT-1        | `LOCAL-WRITE-ACT-1`        | Planned; not yet implemented |
| Combined clean run | `LOCAL-RC-1`               | Required before AWS          |

Passing `LOCAL-RTA-1` unlocks the next local stage only. It is not production
RTA-1 and does not authorize deployment, visibility, writes, authority, or
machine execution.

## Provision

Run from the isolated implementation worktree. Replace SHAs only with explicitly
accepted full values.

```bash
python3 ops/control-plan-read-local/orchestrate.py provision \
  --release-sha 8095bfe37550200da00ecb554edc646febf8aff9
```

Provisioning installs PostgreSQL/PostGIS, Redis, loopback InfluxDB, promtool,
PM2, central auth, and one service-local `.venv` from each of the four tracked
requirements manifests. It creates local-only credentials inside the guest and
stores them in mode-600 files. It never returns their values to macOS.

The Prometheus Debian package is used only for `promtool`; its Prometheus and
node-exporter services are disabled to prevent wildcard listeners.

## Run Stage 0 and Stage 1

```bash
python3 ops/control-plan-read-local/orchestrate.py run-stage --stage LOCAL-BASE-0 \
  --release-sha 8095bfe37550200da00ecb554edc646febf8aff9 \
  --frontend-sha 3a16498a60927996ac38e741b276150968d0cadc

python3 ops/control-plan-read-local/orchestrate.py run-stage --stage LOCAL-RTA-1 \
  --release-sha 8095bfe37550200da00ecb554edc646febf8aff9 \
  --frontend-sha 3a16498a60927996ac38e741b276150968d0cadc
```

`LOCAL-RTA-1` preserves the twelve mandated steps. The local runner invokes the
tracked runtime gate, ecosystem, wrappers, migrations, monitoring preflight,
and bearer verifier. It enforces bearer verification before `pm2 save`.

The gate requires:

- at least 512 MiB `MemAvailable`;
- no more than 1 GiB used swap;
- no application-port conflict or non-loopback TCP listener;
- Scheduler migration parity through `0013_operator_approved_execution`;
- ROS parity through `0003_daily_requirement_producer`;
- BFF migration 009 presence and recorded file hash;
- promtool and repository preflight success;
- four ready loopback services for 300 continuous seconds;
- unchanged PM2 restart counts;
- missing and malformed bearer rejection;
- authenticated Scheduler/BFF list reads and missing-detail behavior;
- BFF `no-store` behavior;
- logout followed by rejected refresh reuse;
- every producer, command, execution, write, and visibility gate dark.

On failure, the runner stops only `flow-monitoring`, `scheduler`,
`ros-gis-integration`, and `bff-water-planning`. It does not save the failed PM2
set. Migrations are not rolled back.

## Evidence

Collect sanitized evidence without exposing the isolated guest filesystem:

```bash
python3 ops/control-plan-read-local/orchestrate.py collect \
  --release-sha 8095bfe37550200da00ecb554edc646febf8aff9 \
  --evidence-dir coding-logs/evidence/local-rta-1
```

The evidence bundle contains stage JSON, state, and `SHA256SUMS`. It rejects
secret-shaped keys, bearer values, credential-bearing URLs, and credential
material before writing mode-600 files.

The 2026-07-23 rehearsal preserved its first otherwise-successful attempt as
`evidence-with-wildcard` after listener inspection found package-started
Prometheus services on ports 9090 and 9100. Those services were disabled, the
gate was strengthened, and Stage 0/1 were rerun from a new evidence directory.

## Current accepted local result

- Backend: `8095bfe37550200da00ecb554edc646febf8aff9`
- Frontend: `3a16498a60927996ac38e741b276150968d0cadc`
- `LOCAL-BASE-0`: PASS
- `LOCAL-RTA-1`: PASS
- Stability: 300 seconds, restart-count equality
- Final capacity: more than 9 GiB available, 0 MiB used swap
- Final listeners: loopback only
- PM2 saved only after bearer success
- AWS actions: none

These readings are local evidence and do not describe AWS capacity or runtime
state.

## Next local work

Implement and pass `LOCAL-AC-1` and `LOCAL-READ-ACT-1` against deterministic
local sources and the real service routes. Continue through each named local
gate, then rebuild disposable state and pass `LOCAL-RC-1`. Only that final pass
allows a separately authorized AWS promotion turn to begin.
