# GO-READ-1 Read-only Gate Route Coding Log

Created: 2026-07-24 06:36:59 +07
Authoritative baseline: `origin/main` at `1b1c33d860bb2e15938b34585b8451e405052b69`

## Scope contract

Implement and land GO-READ-1 from the synchronized execution plan in
`coding-logs/2026-07-23-22-11-44 Coding Log (be-fe-synchronized-optimal-path).md`:

- Add `/read-only/gates/[id]` in `services/scada-gate-control-web`.
- The exact route ID may drive only the gate-status GET.
- Do not import or render device-command, horn, or control-authority actions.
- Signed-out and upstream-unavailable states fail closed.
- Preserve the existing command-capable `/gates/[id]` route unchanged.

This slice is being developed in an isolated worktree from exact current
`origin/main`; the dirty primary checkout remains untouched.

## Workflow notes

- The pinned Next.js 16.2.9 dynamic-route and page-file guidance was read before
  production edits.
- Auggie semantic search was skipped because the available interface cannot
  enforce the required two-second deadline. Direct file inspection and
  exact-string search are used instead.

## TDD log

### RED

Command:

`npm test -- --run 'src/lib/read-only-gate-status.test.ts' 'src/app/read-only/gates/[id]/page.test.tsx'`

Expected failure: both suites failed to resolve the intentionally absent
`read-only-gate-status` client and `/read-only/gates/[id]` page.

### GREEN

Added the GET-only status client and protected static-status page. The focused
command now passes `2` files and `9` tests, covering:

- exact encoded gate-status GET with bearer forwarding;
- one same-path GET retry after a 401 refresh;
- fail-closed authentication refresh behavior;
- exact route-ID forwarding;
- observed and unavailable rendering;
- signed-out denial before status access;
- zero device-command controls and forbidden imports.

## Quality gates

- `npm run typecheck` - passed.
- `npm run lint` - passed.
- `npm test` - passed three consecutive times, each with `32` files and `176`
  tests.
- `npm run build` - passed; Next.js emitted the new dynamic route
  `/read-only/gates/[id]`.
- `git diff --check` - passed.
- Exact-string inventory found no forbidden command/control import in production
  GO-READ-1 files.

The build retains the repository's existing multiple-lockfile workspace-root
warning; compilation, type checking, page generation, and route emission all
completed successfully.

## Independent QCHECK and remediation

Independent read-only QCHECK reported no critical or high findings and four
lower-severity gaps:

1. malformed HTTP-200 status data could reach nested rendering;
2. an initially absent bearer could still cause an unauthenticated GET;
3. this web service was outside the control-plane CI workflow;
4. negative symbol regexes alone were an incomplete import/mutation boundary.

All were remediated:

- Added focused RED tests for a missing initial bearer and malformed successful
  response. Both failed against the initial implementation as expected.
- The GET-only client now performs zero network requests without a bearer and
  validates the complete gate-status shape before returning it; malformed JSON
  or shape fails as upstream `502`.
- Static tests now enforce an import allowlist and reject all common HTTP
  mutation methods.
- The control-plane workflow now includes the web-service path and a dedicated
  `scada-gate-control-web-tests` job running install, typecheck, lint, Vitest,
  and production build. The workflow parses as valid YAML.

Post-remediation gates:

- Focused: `2` files, `11` tests passed.
- TypeScript and ESLint passed.
- Full Vitest passed three consecutive times, each with `32` files and `178`
  tests.
- Production build passed and retained the dynamic read-only route.

## Formal g-check

Reviewed the complete staged GO-READ-1 slice: GET-only client and validation,
protected page, focused tests, CI wiring, Coding Log, and pointer.

### Findings

No critical, high, medium, or low findings remain.

### Evidence and residual notes

- The production import graph contains no device-command component or
  POST-capable client. The one type-only `GateStatus` import is erased at build
  time; the exported runtime client exposes only `getGateStatus`.
- Missing bearer, failed refresh, non-2xx response, invalid JSON, and malformed
  successful payloads all fail closed.
- The new page renders observed values or an unavailable state with zero gate
  actuation controls; the existing command-capable route is unchanged.
- The backend route contract was cross-checked against
  `services/scada-gate-control/src/state/store.ts` and
  `services/scada-gate-control/src/api/routes.ts`.
- `git diff --cached --check` passes.
- GitHub Actions remains repository-documented as billing-locked, so local gates
  remain authoritative until billing is restored; the new job is ready to run
  when the workflow resumes.
