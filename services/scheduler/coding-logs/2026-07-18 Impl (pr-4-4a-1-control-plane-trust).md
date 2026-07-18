# PR 4.4a-1 — scheduler control-plane trust hardening (impl log)

**Date:** 2026-07-18 · **Base:** main `5832aec6` · **Branch:** `feat/scheduler-control-plane-trust`
**Plan:** `coding-logs/2026-07-18 Plan (pr-4-4a-4-4b-control-plane-hardening).md` (sub-PR 4.4a-1).
First sub-PR of the split PR 4.4a (trust). The CRITICAL fix the review said must land before any outbox work.

## What shipped (fail-closed throughout)
- **Strong secret** (`core/config.py`): `jwt_secret_key` must be ≥32 bytes, not blank/single-repeat, not a
  short-period repetition (`ab`×16, `abcd`×8), ≥5 distinct chars, and not a well-known default (`change-me`…)
  — a weak secret breaks `Settings()` so the service cannot boot on a guessable key. `jwt_algorithm` pinned HS256;
  `jwt_claim_policy_mode` explicit `compat|strict`; added `jwt_issuer/jwt_audience/jwt_access_token_type/
  jwt_clock_skew_seconds/control_plan_authorization_policy_version`.
- **Staged claim validation** (NEW `core/auth.py` + `core/deps.py`): `verify_token` pins HS256 from settings
  (never the token header), requires `exp`, bounded skew, then `validate_access_token_claims`. `compat` accepts
  legacy tokens missing iss/aud/jti/roles but rejects any present-but-wrong claim (forgery signal); `strict`
  requires exact iss/aud/type + non-blank jti + non-empty roles.
- **Fail-closed revocation** (`core/deps.py`): decode FIRST (garbage→401, no store I/O); missing store client→503;
  store exception→503; hashed keys only (issuer-bound jti digest, or sha256(token) fallback — never raw token/jti,
  logs included). **Dual-read** the new hashed key AND the legacy `token:blacklist:<raw-token>` key so an
  as-yet-unmigrated logout/auth writer still revokes. WS path symmetric.
- **Hierarchical RBAC** (`core/deps.py` + endpoints): admin>supervisor>operator>field_team; a matching effective
  role is ALWAYS required (role-less is 403 even in compat — compat relaxes only claim SHAPE, not authorization).
  Matrix: draft/get/ledger/**cancel**=require_operator; review/invalidate/supersede=require_supervisor;
  approve-for-shadow=require_supervisor + `require_strict_approval_policy` (503 in compat → a compat token can
  read/draft but can never mint a *trusted* approval).
- **Approval evidence + freeze v2** (`core/control_plan_lifecycle.py` + lifecycle service + `ShadowApprovalRequest`):
  approve requires nonblank `reason` + 1–20 nonblank `evidence_refs`; the transition document becomes v2
  `{schema_version:2, lineage_freeze, authorization_evidence}`; `verify_shadow_approval_freeze` recomputes and
  compares ONLY `lineage_freeze` (evidence isn't reconstructable) and still accepts legacy v1 bare freezes.
  `is_trusted_shadow_approval` validates the COMPLETE strict-mode evidence (supervisor role, hashed identity,
  request id, non-empty refs) — a forged one-field `{"claim_policy_mode":"strict"}` is not trusted; supersede
  rejects any non-trusted successor approval; corrupt successor doc → 503 (not 500).
- **Request id** (`api/middleware/request_id.py` + `main.py`): bounded `^[A-Za-z0-9._-]{1,128}$` via `fullmatch`
  (rejects trailing newline); `RequestIDMiddleware` wired (fail-open `AuthMiddleware` left UNWIRED).
- **Infra** (`infra/pm2/build-irrigation-config.ts` + spec): scheduler `JWT_SECRET_KEY`→`requiredEnv` +
  `JWT_ISSUER/JWT_AUDIENCE/JWT_ACCESS_TOKEN_TYPE/JWT_CLAIM_POLICY_MODE`.

## Gate
Bare pytest: **348 passed / 6 skipped ×3** (baseline 283+6; +65 net trust tests, no new skips, nothing weakened).
pyflakes clean. infra/pm2 jest 12 passed + typecheck clean.

## 2-tier QCHECK (both tiers ran; findings fixed)
- Tier-1 (Opus 4.8 adversarial): safe to merge, no CRITICAL/HIGH; positively verified the fail-closed core. 2 MEDIUMs.
- Tier-2 (Codex gpt-5.6-sol high): 4 HIGH + 2 MED + 1 LOW (uncorrelated with tier-1 on the extras). ALL fixed:
  role-less-bypass removed; patterned-secret rejection; revocation dual-read; strict-jti staged+warned;
  is_trusted full-evidence validation; request-id fullmatch; supersede corrupt→503. Each fix is regression-tested.

## Deferred / external (documented, NOT executed here)
- `services/scheduler/.env.example` was blocked by the `protect-files.sh` guardrail (glob matches `.env`) — deferred
  (non-load-bearing doc; the load-bearing PM2 `requiredEnv` + code fail-closed are in). Intended contents saved to
  scratchpad.
- External ops (unchanged from the plan): rotate the live signing secret + upgrade the issuer to emit
  iss/aud/type/sub/**jti**/roles BEFORE flipping `JWT_CLAIM_POLICY_MODE=strict` (strict rejects no-jti tokens by
  design); the real `.env`/PM2 host env must supply a strong secret + issuer/audience/mode or the service
  intentionally refuses to boot; deploy the matching hashed-key revocation writer (or rely on dual-read during
  migration); inventory + invalidate any pre-policy shadow approvals via the API.
