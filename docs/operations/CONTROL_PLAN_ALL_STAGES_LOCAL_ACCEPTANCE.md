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
| FE-5 / FE-6        | `LOCAL-WRITE-UI-1`         | Implemented; latest campaign passed |
| DEC-W4             | `LOCAL-PERSIST-ONLY-1`     | Implemented; latest campaign passed |
| WRITE-ACT-1        | `LOCAL-WRITE-ACT-1`        | Planned; not yet implemented |
| Combined clean run | `LOCAL-RC-1`               | Required before AWS          |

Passing `LOCAL-RTA-1` unlocks the next local stage only. It is not production
RTA-1 and does not authorize deployment, visibility, writes, authority, or
machine execution.

## Provision

Run from the isolated implementation worktree. Replace SHAs only with explicitly
accepted full values. Canonical provisioning accepts no live dependency
downloads. First build the ARM64 dependency closure in the explicitly
non-authoritative diagnostic guest:

```bash
accepted_backend_sha=REPLACE_WITH_ACCEPTED_40_CHARACTER_BACKEND_SHA
accepted_frontend_sha=REPLACE_WITH_ACCEPTED_40_CHARACTER_FRONTEND_SHA
dependency_bundle=/absolute/external/evidence/dependencies-${accepted_backend_sha}.tar.gz

python3 ops/control-plan-read-local/orchestrate.py build-dependencies \
  --release-sha "$accepted_backend_sha" \
  --frontend-sha "$accepted_frontend_sha" \
  --accept-later-origin-main \
  --confirm-diagnostic-build \
  --dependency-bundle "$dependency_bundle"
```

The frontend value must be the explicitly reviewed full SHA at the clean Smart
CMS `origin/main`. Historical frontend SHAs below are evidence identities, not reusable defaults.

The builder cold-acquires and checksum-indexes the Debian/PostgreSQL/PostGIS,
InfluxDB, Node 22.23.1/npm 10.9.8, PM2 5.4.3, four Python wheel closures, five
application Node lockfile closures, Playwright 1.54.2, and Chromium surfaces.
It binds the manifest to Debian 12 ARM64, the exact backend/frontend SHAs, every
committed requirements/lockfile hash, the ARM64 Python wheel-closure lock, and
every bundled byte. Public registries are allowed only in this diagnostic build
lane. A bundle-build failure has no
acceptance meaning and must not trigger a canonical guest retry.

## Non-authoritative three-stage rehearsal

A separate rehearsal grant may create only the fixed
`munbon-control-plan-rehearsal` guest and run only the ordered `LOCAL-BASE-0 → LOCAL-RTA-1 → LOCAL-AC-1` prefix. The grant must name the exact
backend and frontend SHAs, dependency bundle and checksum, Bangkok operational
date with unused RID weeks, and fresh evidence destinations. A rehearsal grant does not authorize canonical guest replacement, canonical campaign execution,
deployment, activation, visibility, writes, or AWS action.

After the exact candidates and offline dependency closure are ready, use the
separately authorized values:

```bash
rehearsal_as_of_date=REPLACE_WITH_AUTHORIZED_BANGKOK_DATE
rehearsal_bootstrap_failure_dir=/absolute/external/evidence/rehearsal-bootstrap-failure-${accepted_backend_sha}
rehearsal_evidence_dir=/absolute/external/evidence/rehearsal-${accepted_backend_sha}

python3 ops/control-plan-read-local/orchestrate.py provision-rehearsal \
  --release-sha "$accepted_backend_sha" \
  --frontend-sha "$accepted_frontend_sha" \
  --accept-later-origin-main \
  --dependency-bundle "$dependency_bundle" \
  --dependency-bundle-sha256 "$dependency_bundle_sha256" \
  --bootstrap-failure-dir "$rehearsal_bootstrap_failure_dir"

python3 ops/control-plan-read-local/orchestrate.py run-rehearsal-stage --stage LOCAL-BASE-0 \
  --release-sha "$accepted_backend_sha" \
  --frontend-sha "$accepted_frontend_sha" \
  --accept-later-origin-main \
  --as-of-date "$rehearsal_as_of_date"

python3 ops/control-plan-read-local/orchestrate.py run-rehearsal-stage --stage LOCAL-RTA-1 \
  --release-sha "$accepted_backend_sha" \
  --frontend-sha "$accepted_frontend_sha" \
  --accept-later-origin-main \
  --as-of-date "$rehearsal_as_of_date"

python3 ops/control-plan-read-local/orchestrate.py run-rehearsal-stage --stage LOCAL-AC-1 \
  --release-sha "$accepted_backend_sha" \
  --frontend-sha "$accepted_frontend_sha" \
  --accept-later-origin-main \
  --as-of-date "$rehearsal_as_of_date"

python3 ops/control-plan-read-local/orchestrate.py collect-rehearsal \
  --release-sha "$accepted_backend_sha" \
  --frontend-sha "$accepted_frontend_sha" \
  --accept-later-origin-main \
  --as-of-date "$rehearsal_as_of_date" \
  --evidence-dir "$rehearsal_evidence_dir"
```

Successful collection requires the exact three PASS manifests and writes
`REHEARSAL-SUMMARY.json` with `acceptance_evidence=false`, six explicitly
unreached stages, and `REHEARSAL-OUTER-SHA256SUMS`. It never writes
`SHA256SUMS` or `OUTER-SHA256SUMS`; its verified inner index is renamed to
`REHEARSAL-SHA256SUMS`. It cannot satisfy `successful_closed` and cannot be
appended as campaign acceptance evidence.

On the first rehearsal stage failure, stop immediately and use only:

```bash
python3 ops/control-plan-read-local/orchestrate.py collect-rehearsal-partial-failure \
  --release-sha "$accepted_backend_sha" \
  --frontend-sha "$accepted_frontend_sha" \
  --accept-later-origin-main \
  --as-of-date "$rehearsal_as_of_date" \
  --evidence-dir "$rehearsal_evidence_dir"
```

This recovery keeps `acceptance_evidence=false`, adds the
`non_authoritative_rehearsal` evidence kind, and writes
`REHEARSAL-SHA256SUMS` and `REHEARSAL-PARTIAL-OUTER-SHA256SUMS`, both of which
the campaign-ledger validator rejects.

For provisioning failure, do not call a stage collector. Provisioning already collects and finalizes this bundle automatically at
`$rehearsal_bootstrap_failure_dir`. If that destination exists, preserve and
verify it; do not run a second collector against the same path.

Use the standalone collector below only when provisioning reports
`bootstrap_linux_failed_and_failure_collection_failed` (or was interrupted
before collection completed) **and** the authorized destination does not
exist. It retries recovery of only the sanitized bundle from the preserved
fixed guest:

```bash
python3 ops/control-plan-read-local/orchestrate.py collect-rehearsal-bootstrap-failure \
  --bootstrap-failure-dir "$rehearsal_bootstrap_failure_dir"
```

The rehearsal bootstrap collector adds `REHEARSAL-BOOTSTRAP-SUMMARY.json` with
`acceptance_evidence=false` and writes only
`REHEARSAL-SHA256SUMS` inside the bundle and
`REHEARSAL-BOOTSTRAP-OUTER-SHA256SUMS`, which the campaign ledger rejects.

Do not repair, reprovision, or promote the rehearsal guest. Guest cleanup needs
separate authority after the frozen host evidence verifies.

Verify the resulting digest, choose a new external failure destination, and
then provision:

```bash
dependency_bundle_sha256="$(shasum -a 256 "$dependency_bundle" | awk '{print $1}')"
bootstrap_failure_dir=/absolute/external/evidence/bootstrap-failure-${accepted_backend_sha}

python3 ops/control-plan-read-local/orchestrate.py provision \
  --release-sha "$accepted_backend_sha" \
  --frontend-sha "$accepted_frontend_sha" \
  --accept-later-origin-main \
  --dependency-bundle "$dependency_bundle" \
  --dependency-bundle-sha256 "$dependency_bundle_sha256" \
  --bootstrap-failure-dir "$bootstrap_failure_dir"
```

Provisioning verifies the outer archive digest, every inner artifact digest,
the environment contract, exact source SHAs, and all committed dependency
inputs before it changes runtime state. npm lifecycle scripts and Prisma
generation run only in the diagnostic build; canonical bootstrap extracts their
checksum-bound ARM64 `node_modules` outputs without invoking npm. pip runs with
`--no-index --find-links`; Playwright and Chromium come from the bundle. One
explicit Node 22/npm 10 toolchain runs PM2, auth seeding,
central auth, SCADA, Gate Web, Smart CMS, and stage preflight.

The durable state machine is `created → dependency-staged → runtime-reset →
ready`; `failed` and `interrupted` are terminal. PostgreSQL recreation, Redis
flush, evidence rotation, and runtime quiescing occur only after
`dependency-staged`. The ready owner marker becomes visible only in the final
ownership step. A failed or interrupted ownerless guest is evidence-only: it cannot resume provisioning or
run acceptance. There is no automatic transport retry, guest replacement, or
reprovision of a ready guest.

On failure, the guest writes a mode-600 sanitized bundle containing only a
stable classification, phase/substep, exit code, exact SHAs, tool versions, and
redacted log. The host streams it without requiring an owner marker, verifies
the inner checksums, and writes an outer checksum index before returning the
safe error code. Before the offline closure installs Python, a Bash-only writer
records the initial state and emits the same checksum-bound terminal contract
with only a controlled failure line. Python takes over the state machine after
installation; if an executable but unusable interpreter cannot publish a
failure, the Bash writer remains the fallback. If automatic collection is interrupted, recover it explicitly
without modifying the guest:

```bash
python3 ops/control-plan-read-local/orchestrate.py collect-bootstrap-failure \
  --bootstrap-failure-dir "$bootstrap_failure_dir"
```

Do not manually complete installs, import an unverified cache, snapshot a
partial guest as fresh, or classify pre-stage provisioning as an acceptance
stage failure. Guest deletion or a new canonical attempt always needs separate
authorization after the failure bundle verifies.

Canonical replacement authority must name the exact preserved guest ID and
machine name, the new campaign and attempt ceiling, accepted candidates,
dependency checksum, evidence destination, Bangkok date, and clean RID weeks.
Before deletion, one operator must validate that exact stable ID against its
name, shape, owner, candidate, dependency, stage state, failure evidence, and
checksums; immediately re-read the inventory, delete only that stable ID using
the validated Orb command, and verify it is absent. Stop if Orb cannot address
the stable ID or if any field changes. Never delete by name alone and never
modify or replay the exhausted guest.

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
- ROS parity through `0004_dataset_version_identity_immutable`, including exact
  catalog proof of `dataset_versions_identity_is_immutable` and
  `dataset_versions_no_truncate` on `ros_gis.dataset_versions`;
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
Playwright workflow across three browser contexts (two operator, one field
team). Each transition verifies the state and every preceding stage checksum,
rechecks clean backend and frontend SHAs, and binds the state to hashes of the
installed harness files. It rejects secret-shaped keys, bearer values,
credential-bearing URLs, and credential material before writing mode-600 files.

### `LOCAL-WRITE-UI-1` denial, outage, and logout evidence

The stage records only what it actually observes. In particular it does **not**
claim that planning-depth reads survive an outage, because they do not — both
the roster and the active-submission reads resolve an operator principal through
the scheduler.

| Drill | How it is induced | What is proven |
|---|---|---|
| Field-team denial | A seeded `field_team` user (no operator rights) signs in | roster `403`, active `403`, the `ส่งแผน` control is **not rendered**, the denial banner is shown, and no write succeeds |
| Scheduler outage | The stage runs `pm2 stop scheduler` once the browser signals ready, then restores it through the bounded guarded restart (retries + independent pm2/readiness verification) | roster `502`, active `502` (every upstream failure collapses to 502 at the proxy), the control is **not rendered**, the unavailable banner is shown, and no write succeeds |
| Logout | The real `POST /api/auth/logout` for every context | a success status, a redirect that lands on `/login` on both navigation and reload, and — per browser context — reuse of that context's OWN pre-logout refresh credential rejected with `401`. A separate direct-auth session is probed identically and its non-`401` reuse also hard-fails the stage. |

The discriminator is two-sided: each drill must show its own banner **and** must
not show the other's, so an outage can never be recorded as a permission denial.
That matters because the product collapses `not-requested`, `loading`,
`unauthenticated`, and `unavailable` into a single state, so the outage banner is
also what an expired session renders. The explicit `403`/`502` read probes carry
the primary discrimination; the banners corroborate it.

Each drill reads the panel only after the application's **own** roster and active
requests have settled, and records the statuses they returned. That ordering is
load-bearing: the panel renders its "upstream unavailable" banner from the
`not-requested` placeholder, so reading it too early would let the outage drill
pass having asked nothing. The recorded statuses must match the drill's explicit
probes, so a banner alone can never stand in for a read.

The browser run is **loopback-only**: every context aborts any request that
leaves `http://127.0.0.1:9999`. The planning workspace mounts a map that would
otherwise fetch tiles and marker icons from `tile.openstreetmap.org`,
`server.arcgisonline.com`, and `unpkg.com` — none of which any assertion here
depends on, and all of which would stall an isolated guest.

Readiness is **neither** network quiescence **nor** any DOM element. `networkidle`
never settles while third-party tiles retry; the `draft-action-bar` container
renders from local draft state before the reads are issued; and the "upstream
unavailable" banner renders from the *not-requested* placeholder, so it is
present from the first client render in every drill. Each of those would resolve
instantly and gate nothing. Readiness is therefore the app's own roster and
active reads completing, observed inside the page and flushed through a render.

Any snapshot, subprocess, coordination, or restore FAILURE (Exception-class)
raises and fails the stage with a `-failure.json` manifest; the scheduler is
restored through a bounded guarded restart (retries plus an independent
pm2/readiness final-state check whose verdict is authoritative and never masks
the primary error), the restoration report rides into the evidence on success
and into the failure manifest otherwise, and if a restore also fails the error
names both it and the original finding. An operator interrupt (Ctrl-C /
`SystemExit`) is NOT a stage verdict: it makes a bounded best-effort to bring the
scheduler back, then propagates with its own process exit semantics and writes
NO stage manifest — recording a `FAIL` for an abort would stamp a contradiction
beside an already-written `PASS` when the interrupt lands just after a stage
completed.

The browser JSON is sanitizer-checked, written as
`LOCAL-WRITE-UI-1-browser-result.json`, and checksum-indexed before its
acceptance predicates run. A validator rejection records every disagreeing
predicate as a stable code in the checksum-indexed failure manifest; it never
records credentials, cookies, tokens, or arbitrary exception text. This makes a
failure replayable without weakening the generic stage verdict.

### Disposable WRITE-UI diagnostic lane

Diagnostics are not acceptance evidence. Clone or snapshot the guest only after
collecting the frozen evidence, update that clone to the diagnostic candidate,
and use a fresh `--as-of-date` whose RID week has not been submitted in the
cloned database. Run the stage runner directly on the clone with `--diagnostic`
and a new evidence root:

```bash
orb -m munbon-control-plan-write-ui-diagnostic -u root \
  install -d -o munbon -g munbon -m 0700 \
  /var/lib/munbon-local-acceptance/write-ui-diagnostic

orb -m munbon-control-plan-write-ui-diagnostic -u munbon \
  python3 /opt/munbon/harness/run-stage-suite.py LOCAL-WRITE-UI-1 \
  --release-sha "$diagnostic_backend_sha" \
  --frontend-sha "$diagnostic_frontend_sha" \
  --execution-kind canonical \
  --as-of-date "$fresh_diagnostic_date" \
  --evidence-root /var/lib/munbon-local-acceptance/write-ui-diagnostic \
  --diagnostic
```

The runner rejects `--diagnostic` on the canonical acceptance machine, on the
canonical acceptance evidence root, or on a root containing `stage-state.json`.
Diagnostic success writes
`LOCAL-WRITE-UI-DIAGNOSTIC.json` with `acceptance_evidence=false`; failure uses
the same explicit label. Neither path advances acceptance stage state. Always
verify the backend write flag is false, all four backend services are ready,
and no listener remains on port 9999 after the run.

Diagnostic mode also compares two existing operator sessions while holding
bearer semantics constant: the primary session logs out with page-origin
`fetch` using `credentials: "same-origin"`, while the second uses Playwright's
request context. `logout_transport_diagnostic` retains only the transport,
session count, refresh-session name/domain/path/Secure/SameSite metadata,
logout status, and refresh-reuse status. It never retains credential values,
headers, bodies, or raw stderr. Interpret page-origin success plus reuse 401
against request-context 401/200 as a harness transport defect; page-origin 401
implicates the local frontend cookie/proxy path; logout success plus reuse 200
implicates central-auth revocation. These classifications remain diagnostic,
not stage acceptance.

The 2026-07-23 rehearsal preserved its first otherwise-successful attempt as
`evidence-with-wildcard` after listener inspection found package-started
Prometheus services on ports 9090 and 9100. Those services were disabled, the
gate was strengthened, and Stage 0/1 were rerun from a new evidence directory.

## Current local result

The latest canonical campaign is acceptance-truthfully **9 passed / 0 failed /
0 unreached** on one fresh guest and database:

- Campaign: `2026-08-20-nine-stage-orbstack-7f032c4c-attempt-1`
- Backend: `7f032c4c20e7f9cdd443d64f7adbeb37342ff190`
- Frontend: `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`
- Dependency archive: `89a26cbd783b21037acd3ce2f1e116f0e69ba8ea0d1667be8b6fda22a1aef7ab`
- Guest ID: `01M0F27Z1GZQ7SQF07XH9M3VQT`
- all nine ordered local stages: PASS
- failed and unreached stages: none
- final visibility, submit, execution, authority, and write flags: false
- authorization: `successful_closed`, attempt 1 of 1
- external frozen archive:
  `../munbon-control-plan-9of9-evidence/2026-08-20-nine-stage-orbstack-7f032c4c-attempt-1/`
- outer index SHA-256:
  `903602d8ae622c5de72ffa31c705782ae663dfd6dc9a53d4450c6aa5e0c1bbef`
- campaign-ledger entry SHA-256:
  `585467a896065b42a40982eb08c1f3447e1b5439928bcca50fc471a7595e51aa`

The strict `collect` action accepted this checksum-bound 9/9 result and remains
9/9-only. Use
`collect-partial-failure` only to preserve an ordered-prefix failure bundle;
its checksum-bound `PARTIAL-SUMMARY.json` and CLI output are explicitly
`acceptance_evidence=false`, and it writes `PARTIAL-OUTER-SHA256SUMS`. The
append-only campaign history is
`docs/operations/control-plan-campaign-ledger.jsonl` and must pass
`validate_campaign_ledger` before it is extended.

### Historical three-stage result

The prior exhausted attempt remains acceptance-truthfully **2 passed / 1
failed / 6 unreached**:

- Backend: `5cfdb2a05b4ea4c2742250845ae55a76816700bd`
- Frontend: `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`
- Dependency archive: `65b08e348b19a6467e44d6778aaa9d7734bfd34c4f87e8b1e8a4051e6561b4c4`
- Guest ID: `01KZSKQ6FY4EVCCY94XGWZ9NDS`
- `LOCAL-BASE-0`, `LOCAL-RTA-1`: PASS
- `LOCAL-AC-1`: FAIL at `manual_requirement_run_not_accepted`
- stages 4–9: unreached
- authorization: attempt 3 of 3 consumed
- external frozen archive:
  `../munbon2-backend-external-evidence/2026-08-12-nine-stage-orbstack-5cfdb2a0-attempt-3/`
- outer index SHA-256:
  `34b952b660ec230ab2d9049b60f6dd8496561ce6e2860b377124c8ae48947ecd`

### Historical seven-stage result

The prior candidate result was acceptance-truthfully **7 passed / 1 failed /
1 unreached**:

- Backend: `0228f495b7708b92cc7526f201687eb5b1441565`
- Frontend: `067b3e22401854f8c6d6db42dc0c5c1872fca6f8`
- stages 1–7: PASS
- `LOCAL-WRITE-UI-1`: FAIL at `write_browser_result_not_accepted`
- `LOCAL-PERSIST-ONLY-1`: not reached
- scheduler restoration: succeeded on attempt 1
- final backend write flag: false
- final backend services: online and ready
- final listener 9999: absent
- frozen archive:
  `coding-logs/evidence/2026-08-09-nine-stage-orbstack-0228f495/`

The rejected browser JSON was not retained by that frozen candidate, so the
historical bundle cannot prove whether one or several predicates disagreed.
The older result below is retained as historical context only.

### Historical six-stage result

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

## Remaining authority boundary

All nine current local acceptance stages are implemented.
The current candidate has genuine 9/9 local acceptance evidence from one
pristine authorized guest, and its `successful_closed` ledger entry binds the
exact backend, frontend, dependency, harness, guest, and outer checksum index.
Future candidates must still refresh the exact identities and rerun the full
contract. Visibility, submit, write, and authority gates remain dark by
default.

Another rehearsal or canonical campaign requires a new separate authorization.
Guest replacement, deployment, and activation remain separately authorized actions.
Every authorized campaign outcome, success or failure, must extend the campaign
ledger with its appropriate checksum-bound evidence. This 9/9 result grants no
`LOCAL-RC-1`, deployment, activation, AWS, or production authority. Promotion
still requires a separately authorized passing `LOCAL-RC-1`, and separate
promotion and AWS authorization.
