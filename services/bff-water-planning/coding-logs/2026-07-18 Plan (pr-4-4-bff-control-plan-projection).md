# PR 4.4 — BFF read-only control-plan projection (unified plan)

**Prepared:** 2026-07-18 · **Base:** main `a8896e08` (post-4.3b) · **Service:** `services/bff-water-planning` only
**Synthesis:** Explore recon + Codex gpt-5.6-sol xhigh (`scratchpad/codex-plan-4-4.md`). Roadmap §U3.7.
Dep 4.3b merged.

## 1. Overview
Expose four authenticated, READ-ONLY BFF projections over the scheduler's two control-plan GET routes:
plan detail, prediction coverage, ledger, and lifecycle history. Strict validated pass-through
(mirror every upstream field/lineage artifact) — NO new status vocabulary, NO success booleans, NO
fabricated delivery numbers. Preserve upstream unavailable/infeasible/invalidated/stale states. No
writes, no list (upstream has none), no scheduler/BFF-DB change.

## 2. Files (bff-water-planning only)
New: `pytest.ini` (testpaths=tests, asyncio_mode=strict — recon found NO pytest config and bare pytest
collects legacy networked scripts); `src/schemas/control_plan.py` (strict mirrors);
`src/api/routes/control_plans.py` (bearer-gated router + 4 GET handlers); `tests/unit/test_control_plan_projection.py`.
Modified: `src/clients/scheduler_client.py` (add typed fail-closed errors + injectable
`transport` + the two authenticated read methods; legacy schedule methods untouched);
`src/clients/__init__.py` (export the new error type, like `WaterRequirementClientError`);
`src/main.py:103-106` (mount the new router in the inline import block); `CLAUDE.md`.
**Unchanged:** the scheduler service, any migration, BFF DB, write APIs, settings fields, secrets.

## 3. Fail-closed scheduler client (mirror `water_requirement_client.py` + scheduler `control_flow_client.py` idiom)
Constructor extended compatibly: `__init__(self, base_url=None, *, transport: httpx.AsyncBaseTransport|None=None)`
— `transport` lets tests inject `httpx.MockTransport` (no monkeypatch/network). Base URL =
`settings.scheduler_url` (`SCHEDULER_URL`; NOT the duplicate `scheduler_service_url`).
Typed errors: `SchedulerAuthError(status, detail)`, `SchedulerControlPlanNotFoundError(detail)`,
`SchedulerUnavailableError`, `SchedulerContractError`, `SchedulerUpstreamError`.
Methods (both call a shared `_get_control_plan_document(path, bearer_token)` that sends
`Authorization: Bearer <token>`, requires a JSON object on 200, NEVER returns None/[]/`{"status":"failed"}`,
and logs path/plan/version/status but NEVER the token):
- `get_control_plan_projection(plan_id, plan_version, bearer_token) -> dict` → GET
  `/api/v1/control-plans/{plan_id}/versions/{plan_version}`.
- `get_control_plan_ledger(plan_id, plan_version, bearer_token) -> dict` → GET `.../ledger`.

Error taxonomy (preserve upstream `{"detail":...}`; never leak raw transport/host):
| Scheduler | Client → | BFF |
|---|---|---|
| 200 valid object | dict | validate → 200 |
| 200 malformed/non-object | SchedulerContractError | 502 |
| 401 / 403 | SchedulerAuthError(status) | same status, retain detail |
| 404 | SchedulerControlPlanNotFoundError | 404, retain detail |
| 503 | SchedulerUnavailableError | 503, retain detail |
| timeout/connect/DNS | SchedulerUnavailableError | 503 (generic detail) |
| other 4xx/5xx | SchedulerUpstreamError | 502 |
| invalid BFF UUID/version | (no call) | FastAPI 422 |

## 4. Routes + response schema
Router `APIRouter(prefix="/api/v1/control-plans", tags=["control-plans"])`, `Path(gt=0)` on plan_version.
| Route | Upstream call | Response model |
|---|---|---|
| `GET /{plan_id}/versions/{plan_version}` | detail | `ControlPlanProjection` (full mirror) |
| `GET /{plan_id}/versions/{plan_version}/prediction-coverage` | detail | `ControlPlanPredictionCoverage` |
| `GET /{plan_id}/versions/{plan_version}/ledger` | ledger | `ControlPlanLedgerProjection` (full mirror) |
| `GET /{plan_id}/versions/{plan_version}/lifecycle-history` | detail | `ControlPlanLifecycleHistory` |
No `GET /api/v1/control-plans` (no upstream list; do NOT fabricate one).

Strict mirrors — `StrictControlPlanModel(BaseModel)` with `ConfigDict(extra="forbid", protected_namespaces=())`,
**snake_case pass-through** (mirror the scheduler field names exactly — this is validated pass-through,
not a transformed DTO). Detail mirrors ALL `DraftControlPlanResponse` fields (lifecycle_state,
input/draft hashes, requirement_run_id/version, model pins, optimizer_status, prediction_status,
prediction_run_id, prediction_member_statuses[{member,status}], horizon_start/end, model config,
`optimizer_result: dict`, requirements[...], events[...], transitions[{...,transition_document: Optional[dict]}],
created_by/at). Ledger mirrors ALL `ControlPlanLedgerResponse` fields (entries[{...,
{delivered_m3,path_in_transit_m3,remaining_m3}: {lower_bound,nominal,upper_bound}, checkpoint_reasons}],
handover[{gate_id,requirement_ids,is_safe,reasons}], ledger_sha256). `extra="forbid"` makes an upstream
schema drift (missing/renamed/retyped field) → ValidationError → 502 (fail-closed on drift).
Prediction-coverage = the exact lineage + prediction/member statuses subset (NO is_complete/success/
percentage/zero-count). Lifecycle-history = plan identity + derived lifecycle_state + the complete
ordered `transitions` with every `transition_document` verbatim.

`test_bff_plan_projection_retains_exact_lineage` asserts, exactly: plan_id/version, input/draft hashes,
requirement run/version, per-requirement requirement_id/run_id/source_version, model snapshot/release/
content hashes, prediction_run_id, ledger_sha256, and the complete shadow-approval transition document
(its optimizer-result/requirement-set/prediction-response/ledger hashes).

## 5. State preservation
- unavailable → scheduler 503 / transport failure → BFF 503, NO plan/coverage/ledger/delivery/success body.
- infeasible → 200 with the exact optimizer_status/prediction_status/member statuses; preserve empty/
  null upstream ledger values exactly (infeasibility is a valid state, not an error).
- invalidated → preserve `lifecycle_state="invalidated"`, the invalidation transition + reason +
  document, and any `invalidated` ledger row status.
- stale → preserve `requirements[].source_data_status == "stale"` EXACTLY. It is the immutable
  snapshot-time source status, NOT a live ROS-GIS freshness recompute and NOT a synonym for
  unavailable. (Scheduler currently rejects stale at draft time so this is normally `published`; the
  BFF still preserves `stale` if returned. A current-freshness view is a future, separately specified
  contract — out of scope.)

## 6. Auth — forward the operator bearer token
`security = HTTPBearer(auto_error=True)` → `get_operator_bearer_token()` returns `credentials.credentials`;
each route forwards it to the scheduler. The scheduler remains the JWT + Redis-blacklist authority.
Missing header → BFF 403 (matches scheduler's HTTPBearer). Scheduler 401 (invalid/expired/revoked) →
BFF 401; scheduler 403 → BFF 403. Never log/cache/persist/echo the token. NO service token, NO
duplicated JWT logic, NO shared service subject. Deploy note: the operator JWT forwarded via Kong/BFF
must be trusted by the scheduler (same jwt_secret_key) — verify in staging; no silent service-token fallback.

## 7. Functions
`SchedulerClient._get_control_plan_document()`, `.get_control_plan_projection()`, `.get_control_plan_ledger()`;
`get_scheduler_client()` (DI factory, test-overridable); `get_operator_bearer_token()` (HTTPBearer dep);
`_load_control_plan_projection()` (shared client-error→HTTP mapping + strict detail validation, reused by
detail/coverage/history); route handlers `get_control_plan_projection`, `get_prediction_coverage`,
`get_control_plan_ledger`, `get_lifecycle_history`.

## 8. Tests (`tests/unit/test_control_plan_projection.py`; DI-override for routes, MockTransport for client)
Roadmap: **test_bff_preserves_unavailable_prediction_status** (503 → no fabricated coverage body),
**test_bff_plan_projection_retains_exact_lineage** (every hash/id/version survives, full-structure eq).
Client: bearer forwarded to BOTH reads; expected HTTP failures retain status+detail (401/403/404/503);
transport failure → SchedulerUnavailableError; malformed 200 → SchedulerContractError.
Route/state: infeasible members never become completed; invalidated lifecycle + ledger rows preserved
across both projections; stale source_data_status preserved exactly; all 4 routes reject missing bearer
(403); scheduler auth failure (401/403) reaches the caller; malformed scheduler contract (missing/
retyped required field) → 502 with no partial projection; router exposes ONLY GET (no write op);
OpenAPI advertises NO list route; `main.app` registers all 4 projection routes.

## 9. Wiring
| Component | Entry | Registration | Persistence |
|---|---|---|---|
| detail client method | detail/coverage/history GETs | get_scheduler_client() | scheduler JSON; no BFF table |
| ledger client method | ledger GET | get_scheduler_client() | scheduler JSON; no BFF table |
| strict response models | route validation | imports in control_plans.py | Pydantic only |
| bearer forwarding | every route | HTTPBearer dep | Authorization header only |
| control-plan router | operator GET | `main.py` include_router | none |
| scheduler URL | client ctor | existing `settings.scheduler_url` | existing `SCHEDULER_URL` |
| test discovery | bare pytest | new `pytest.ini` | tests/, strict asyncio |

## 10. Risks / rollback
Strict-mirror drift → 502 (intentional fail-closed; monitor BFF 502s after scheduler deploys).
Forwarded operator JWTs must share the scheduler's trust config (verify in staging; no silent service
token). "stale" = snapshot-time source status, not live freshness (document for clients). No list route
(operators must know plan_id+version; discovery = future scheduler contract). Do NOT cache these
projections (stale cache would undermine exact inspection). GET-only → no flag/migration; rollback =
revert router registration / previous image. Then 2-tier QCHECK (Codex gpt-5.6-sol high + Opus 4.8
adversarial), one Conventional-Commit PR (`feat(bff-water-planning): expose read-only control plan
projections`), admin-merge, exact-main verify.
