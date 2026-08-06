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
| AC-1               | `LOCAL-AC-1`               | Implemented and passed       |
| READ-ACT-1         | `LOCAL-READ-ACT-1`         | Implemented and passed       |
| ME-1 / FE-8        | `LOCAL-EVIDENCE-1`         | Implemented and passed       |
| GO-READ-1          | `LOCAL-GO-READ-1`          | Implemented and passed       |
| W1 / W2            | `LOCAL-WRITE-FOUNDATION-1` | Implemented; prior SHA passed |
| FE-5 / FE-6        | `LOCAL-WRITE-UI-1`         | Implemented                  |
| DEC-W4             | `LOCAL-PERSIST-ONLY-1`     | Implemented                  |
| WRITE-ACT-1        | `LOCAL-WRITE-ACT-1`        | Planned; not yet implemented |
| Combined clean run | `LOCAL-RC-1`               | Required before AWS          |

Passing `LOCAL-RTA-1` unlocks the next local stage only. It is not production
RTA-1 and does not authorize deployment, visibility, writes, authority, or
machine execution.

## Provision

Run from the isolated implementation worktree. Replace SHAs only with explicitly
accepted full values.

```bash
accepted_backend_sha=REPLACE_WITH_ACCEPTED_40_CHARACTER_BACKEND_SHA
accepted_frontend_sha=fbd4ce4df0bb0476b7cd402ac1a4e180a91a7792

python3 ops/control-plan-read-local/orchestrate.py provision \
  --release-sha "$accepted_backend_sha" \
  --frontend-sha "$accepted_frontend_sha" \
  --accept-later-origin-main
```

Provisioning installs PostgreSQL/PostGIS, Redis, loopback InfluxDB, promtool,
PM2, central auth, one service-local `.venv` from each of the four tracked
requirements manifests, and the locked Node manifests for SCADA and Gate Web.
It creates local-only credentials inside the guest and stores them in mode-600
files. It never returns their values to macOS.
Reprovisioning first archives the prior evidence directory, stops the harness
runtime, recreates the harness-owned `munbon_local` database, and flushes the
guest-local Redis instance so an exact-candidate run cannot reuse an earlier
requirement publication, plan, session, or cache entry.

The Prometheus Debian package is used only for `promtool`; its Prometheus and
node-exporter services are disabled to prevent wildcard listeners.

## Run the nine implemented stages

```bash
python3 ops/control-plan-read-local/orchestrate.py run-stage --stage LOCAL-BASE-0 \
  --release-sha "$accepted_backend_sha" \
  --frontend-sha "$accepted_frontend_sha" \
  --accept-later-origin-main

python3 ops/control-plan-read-local/orchestrate.py run-stage --stage LOCAL-RTA-1 \
  --release-sha "$accepted_backend_sha" \
  --frontend-sha "$accepted_frontend_sha" \
  --accept-later-origin-main

python3 ops/control-plan-read-local/orchestrate.py run-stage --stage LOCAL-AC-1 \
  --release-sha "$accepted_backend_sha" \
  --frontend-sha "$accepted_frontend_sha" \
  --accept-later-origin-main

python3 ops/control-plan-read-local/orchestrate.py run-stage --stage LOCAL-READ-ACT-1 \
  --release-sha "$accepted_backend_sha" \
  --frontend-sha "$accepted_frontend_sha" \
  --accept-later-origin-main

python3 ops/control-plan-read-local/orchestrate.py run-stage --stage LOCAL-EVIDENCE-1 \
  --release-sha "$accepted_backend_sha" \
  --frontend-sha "$accepted_frontend_sha" \
  --accept-later-origin-main

python3 ops/control-plan-read-local/orchestrate.py run-stage --stage LOCAL-GO-READ-1 \
  --release-sha "$accepted_backend_sha" \
  --frontend-sha "$accepted_frontend_sha" \
  --accept-later-origin-main

python3 ops/control-plan-read-local/orchestrate.py run-stage --stage LOCAL-WRITE-FOUNDATION-1 \
  --release-sha "$accepted_backend_sha" \
  --frontend-sha "$accepted_frontend_sha" \
  --accept-later-origin-main

python3 ops/control-plan-read-local/orchestrate.py run-stage --stage LOCAL-WRITE-UI-1 \
  --release-sha "$accepted_backend_sha" \
  --frontend-sha "$accepted_frontend_sha" \
  --accept-later-origin-main

python3 ops/control-plan-read-local/orchestrate.py run-stage --stage LOCAL-PERSIST-ONLY-1 \
  --release-sha "$accepted_backend_sha" \
  --frontend-sha "$accepted_frontend_sha" \
  --accept-later-origin-main
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
- BFF migration parity through `012_planning_depth_roster_provenance`;
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

`LOCAL-AC-1` seeds deterministic approved GIS and crop sources, runs the real
manual ROS producer through a transient guest-local internal header, proves
missing and invalid headers are rejected with 403, verifies 287 D..D+6
publications and the Zone 6 read, and records the published run hash plus its
section/crosswalk dataset versions and source hashes alongside the approved
scenario hash. It creates a real Flow snapshot, obtains a feasible Scheduler
draft with completed prediction, checks all eight BFF projections plus
missing-plan behavior, and restores ROS and PM2 to the original dark contract.
The manual trigger credential is generated inside the isolated guest, is absent
from the saved dark ROS environment, and is never written to evidence.

`LOCAL-READ-ACT-1` pins Node and Chromium tooling, runs the focused frontend
suite, and makes three independent production builds in the exact
false → true → false order. The browser proof covers signed-out redirect,
login, navigation, list, detail, refresh, direct deep link, missing-plan
projection errors, and one injected ledger-panel failure. Browser traffic is
restricted to loopback control-plan and auth routes. The browser also observes
zero non-read control-plan requests, searches link, button, input, role, and
action attributes for write or authority controls, and proves five mutation or
authority route candidates return 404 or 405. The final build and browser proof
are dark, and no frontend process remains listening.

`LOCAL-EVIDENCE-1` verifies byte-for-byte parity between the backend and
frontend ME-1 contract trees, then prepares append-only held and unavailable
readback evidence inside the disposable local database. All three projections
must return through the real BFF bearer path with `no-store`; the missing-plan
paths must return 404. The evidence browser proves the present, absent,
unavailable, held, and malformed-decoder states independently, validates the
exact read-only Gate Operations href without navigating it, and records zero
product mutation, authority, hold/resume, level, horn, command, or dispatch
requests. The gate finishes by appending a resumed event and rebuilding with
both control-plan flags false.

`LOCAL-GO-READ-1` builds SCADA and Gate Web from the exact accepted backend
SHA, binds both temporary processes only to `127.0.0.1`, and holds them stable
for 300 continuous seconds. A real operator bearer must read the known offline
gate and unknown-gate 404 directly from SCADA with `no-store`. A real Chromium
session then proves signed-out deep-link protection, login, the same-origin
GET-only proxy, at least three live status responses, the read-only UI, and the
unknown-gate state. The runner stops the real SCADA process after a successful
read; the next poll must return 503, show the unavailable alert, and remove the
prior observation. Browser routing blocks every request except exact auth
posts without query strings, the three expected documents, Next static assets,
framework RSC reads, and the two allowlisted status GETs without query strings.
Screenshots cover the live-offline and post-outage states. Cleanup requires
ports 3030 and 9998 to disappear, PM2 identity to remain exact, central auth to
remain ready, every execution/authority/write gate to remain dark, and both
Smart CMS flags to remain false. The same restoration checks run after
readiness, browser, or outage failure; the failure manifest records their result
without replacing the original failed-gate code.

## Evidence

Collect sanitized evidence without exposing the isolated guest filesystem:

```bash
python3 ops/control-plan-read-local/orchestrate.py collect \
  --release-sha "$accepted_backend_sha" \
  --frontend-sha "$accepted_frontend_sha" \
  --accept-later-origin-main \
  --evidence-dir coding-logs/evidence/local-ac-read
```

The evidence bundle contains stage JSON, two GO-READ screenshots, state, and
`SHA256SUMS`. The write UI stage uses `run-write-browser.js` to drive the
Playwright workflow across two browser contexts. Each
transition verifies the state and every preceding stage checksum, rechecks clean
backend and frontend SHAs, and binds the state to hashes of the installed
harness files. It rejects secret-shaped keys, bearer values, credential-bearing
URLs, and credential material before writing mode-600 files.

The 2026-07-23 rehearsal preserved its first otherwise-successful attempt as
`evidence-with-wildcard` after listener inspection found package-started
Prometheus services on ports 9090 and 9100. Those services were disabled, the
gate was strengthened, and Stage 0/1 were rerun from a new evidence directory.

## Current local result

- Backend: `d47db8e3e61219ac6ff791a7b2e6642c5ae2cf70`
- Frontend: `fbd4ce4df0bb0476b7cd402ac1a4e180a91a7792`
- `LOCAL-BASE-0`: PASS
- `LOCAL-RTA-1`: PASS
- `LOCAL-AC-1`: PASS
- `LOCAL-READ-ACT-1`: PASS
- `LOCAL-EVIDENCE-1`: PASS
- `LOCAL-GO-READ-1`: PASS
- Stability: 300 seconds for RTA and GO-READ, restart-count equality
- Final application listeners: loopback only
- Evidence contract: 10 exact files, aggregate SHA-256
  `ab1a19dd4fdc45954569448fdca4db2ede5b208457a2f2cf7c09414a37cde16c`
- Evidence projections: three real bearer-path 200/no-store responses; three
  missing-plan 404 responses
- Browser cases: present, absent, unavailable, held, malformed, and explicit
  empty-intent-is-not-execution
- Gate Operations boundary: signed-out deep-link protection, authenticated
  same-origin status GET, four live responses, unknown-gate 404, forced-outage
  503, and stale-status removal
- Product request inventory: zero forbidden, mutation, or direct-SCADA browser
  requests; zero action controls
- Evidence state: held during visible proof, then resumed
- Final frontend flags: control-plan reads false, evidence reads false, Water
  Planning V2 false, and submit false
- PM2 saved only after bearer success
- Final execution, producer, write, visibility, authority, and machine-command
  gates: dark
- AWS actions: none
- Sanitized archive:
  `coding-logs/evidence/2026-07-26-go-read-main-d47db8e3/`

The result above predates the later source-delivered write-foundation stage.
`LOCAL-WRITE-FOUNDATION-1` subsequently passed at its own exact SHA; that
evidence is not reused for a new candidate.

Every new candidate must be provisioned cleanly and rerun through all nine
implemented stages at its exact SHA. Evidence from a predecessor or a
tree-equivalent squash commit is not reused because the evidence index is
SHA-bound. These readings are local evidence and do not describe AWS capacity
or runtime state.

## Next local work

Complete the authoritative roster, RID-calendar identity, and frontend retry
prerequisites before implementing `LOCAL-WRITE-UI-1`. Keep all write and
authority gates dark by default. Rebuild disposable state and pass `LOCAL-RC-1`
after every named local gate. Only that final pass allows a separately
authorized AWS promotion turn to begin.
