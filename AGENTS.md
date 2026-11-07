# Agent instructions — Munbon backend

Read [CLAUDE.md](CLAUDE.md) for canonical repository-wide development policy and the nearest service `CLAUDE.md` for service-specific rules. This is a standalone-service monorepo: there is no root package workspace or Turborepo gate.

Current status and remaining work: [Development completion register](docs/development/DEVELOPMENT_COMPLETION_REGISTER.md). Historical plan precedence: [Plan supersession index](docs/development/PLAN_SUPERSESSION_INDEX.md). Architecture and Smart Farm/Irrigation Canal boundaries: [CONTEXT.md](CONTEXT.md).

## Agent safety

- Preserve pre-existing dirty/staged/untracked/ignored work, settings and worktrees. Never reset a dirty checkout or infer ownership from age.
- Read the selected Coding Log before work. Do not silently replace a dirty/unrelated `.codex/coding-log.current`; a new log and conflicting pointer switch need explicit authorization.
- Use a session-owned, clean main-based linked feature worktree. Never give a dirty primary checkout to a production implementer; no direct-main push or implicit admin bypass.
- The current session model owns architecture, contracts, meaningful tests/expected RED, production source/config/schema/migrations/infrastructure/executable tooling, environment repair, documentation, logs, independently rerun GREEN, runtime wiring, review disposition and authorized delivery. No external implementation writer, handoff or writer receipt is required.
- Stop and inspect retained evidence and complete diff after unexpected failure; no blind retry, model substitution or rollback. Fix verified logic failures with meaningful regressions and preserve all required assertions. The implementation context cannot certify its own work; use fresh read-only review contexts under `g2-qcheck`.
- Use installed Pi `g2-coding`; formal `g2-check` and `g2-qcheck` orchestration/required independent review are the approved native review mapping. Retain explicit project three-run requirements despite the generic Pi single-run default.
- Never expose credentials, operator environment, raw credential-bearing errors or reusable credential hashes. Do not authenticate with discovered literals. Source cleanup does not prove rotation/history closure.
- Missing integration/lab/hosted/protection evidence is BLOCKED, not a passing skip or permission to weaken assertions. A local static pass cannot certify runtime, production or activation.
- Credential/history/policy/billing operations, DB mutation, notifications, field commands, guest changes, deployment, activation and PR metadata require their own named authority. A plan or source merge grants none of these.
- Account for every session-created worktree on success, blocking or failure; preserve unique work/evidence before removal and leave unrelated worktrees untouched.
