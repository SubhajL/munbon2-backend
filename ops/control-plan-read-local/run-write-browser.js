#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");

let checkpoint = "startup";

const EVIDENCE_ROOT = "/var/lib/munbon-local-acceptance/evidence";
const W2_BASE = "/api/smart-water-backend/water-planning";
const SUBMIT_PATH = `${W2_BASE}/planning-depth-submissions`;
const ACTIVE_PATH = `${SUBMIT_PATH}/active`;
const ROSTER_PATH = `${W2_BASE}/planning-depth-roster`;
// The V2 planning workspace renders at /smart-water/dashboard itself
// (smart-cms-app app/smart-water/dashboard/page.tsx:41-45 -> WaterPlanningWorkspaceV2),
// and that is also where login redirects. There is no /water-planning segment --
// the merged stage navigated to a 404, which is further proof it never ran.
const WATER_PLANNING_PATH = "/smart-water/dashboard";
const ALLOWED_MUTATION_PATHS = new Set([SUBMIT_PATH]);

// The rendered affordance and the two banners the product uses to distinguish a
// permission denial from an upstream outage (PlanningRhsPanel.tsx:497-535). The
// button is only rendered when submitEnabled && policyAllowed && rosterAuthorized,
// so "absent" -- not "disabled" -- is the correct oracle for both drills, and the
// banners are what keep the two states from being mistaken for one another.
// Match the DISTINCTIVE tail of each banner, not its opening words. The openings
// ("ไม่มีสิทธิ์ส่งแผน", "ระบบต้นทางไม่พร้อมใช้งาน") are also prefixes of two
// submitErrorLabel strings (PlanningRhsPanel.tsx:383,387), so matching on them
// would let a transient submit error set the wrong banner flag -- and the two
// flags are asserted mutually exclusive. Each tail below occurs exactly once in
// the component, only in the policy banner (:517 and :522).
const SUBMIT_BUTTON_NAME = "ส่งแผน";
const DENIED_BANNER = "บัญชีของคุณไม่มีสิทธิ์ในการส่งแผนระดับน้ำ";
const UNAVAILABLE_BANNER = "ไม่สามารถตรวจสอบสิทธิ์การส่งได้ในขณะนี้";

function required(name) {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`missing_${name.toLowerCase()}`);
  return value;
}

function assert(condition, code) {
  if (!condition) throw new Error(code);
}

function classifyProductRequest(url, method) {
  const parsed = new URL(url);
  const p = parsed.pathname;
  const m = method.toUpperCase();
  if (p.startsWith("/api/auth/")) return "auth";
  if (p.startsWith("/_next/")) return "framework";
  if (p === "/login" || p === "/") return "document";
  if (p.startsWith(`${W2_BASE}/`) && (m === "POST" || m === "PUT" || m === "DELETE")) {
    return "mutation";
  }
  if (p.startsWith(`${W2_BASE}/`) && m === "GET") return "read";
  if (p.startsWith("/smart-water/")) return "document";
  return "other";
}

/** The truthfulness invariant: a PRODUCT write that actually SUCCEEDED when none
 * was expected. Bound to the response status rather than the request, so a real
 * 403 or 502 probe is evidence of denial -- not a violation. A 2xx to an
 * unallowlisted product path is forbidden even during the armed write phase.
 *
 * The product-path gate is inside the predicate on purpose. The harness logs in
 * three times, and `POST /api/auth/login -> 200` is not a product write; when
 * that gate lived only in the caller it was possible to drop it there and make
 * the stage permanently red while every offline test stayed green.
 */
function isForbiddenWrite({ method, pathname, status, writeExpected }) {
  const m = String(method).toUpperCase();
  if (!["POST", "PUT", "PATCH", "DELETE"].includes(m)) return false;
  if (!String(pathname).startsWith(`${W2_BASE}/`)) return false;
  if (!(Number(status) >= 200 && Number(status) < 300)) return false;
  return !writeExpected || !ALLOWED_MUTATION_PATHS.has(pathname);
}

/** Attach the captured bearer. The Next.js proxy reads ONLY the Authorization
 * header (upstream-guard.ts:66-71) -- a cookie-only request is 401, which would
 * make every denial/outage assertion below meaningless. Returns a new object so
 * the caller's init is never mutated. */
function authorizedRequestInit(token, init = {}) {
  const value = typeof token === "string" ? token.trim() : "";
  if (!value) throw new Error("missing_bearer");
  return {
    ...init,
    headers: { ...(init.headers ?? {}), Authorization: `Bearer ${value}` },
  };
}

function validateControlPath(value, expectedName) {
  const resolved = path.resolve(value);
  if (
    path.dirname(resolved) !== EVIDENCE_ROOT ||
    path.basename(resolved) !== expectedName
  ) {
    throw new Error("coordination_path_invalid");
  }
  return resolved;
}

/** Per-context response boundary. Installed on EVERY context (primary, second,
 * field-team) so a write from any page is visible -- the merged stage watched
 * only the first page.
 *
 * `resolveBucket` is per-CONTEXT, deliberately not a single global phase: the
 * operator pages stay open while the field-team context runs, so a background
 * refetch there would otherwise be recorded as the field team's status and an
 * operator 200 could overwrite the 403 that IS the denial proof.
 */
function installResponseBoundary(context, inventory, resolveBucket) {
  context.on("response", (response) => {
    const request = response.request();
    const pathname = new URL(response.url()).pathname;
    const method = request.method();
    const status = response.status();
    const kind = classifyProductRequest(response.url(), method);
    if (kind === "mutation") {
      inventory.mutations.push(`${method} ${pathname} ${status}`);
    }
    if (isForbiddenWrite({ method, pathname, status, writeExpected: inventory.writeExpected })) {
      inventory.forbiddenWrites.push(`${method} ${pathname} ${status}`);
    }
    const bucket = resolveBucket();
    if (bucket && method === "GET") {
      if (pathname === ROSTER_PATH) bucket.roster_status = status;
      if (pathname === ACTIVE_PATH) bucket.active_status = status;
    }
  });
}

async function waitForControlFile(target, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (fs.existsSync(target)) return true;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error("coordination_timeout");
}

/** Log in through the real form and capture the access token the app itself
 * stores (login body -> data.accessToken, lib/auth/contract.ts:143). */
async function loginAndCaptureToken(page, frontendUrl, email, password) {
  const pending = page.waitForResponse(
    (r) => new URL(r.url()).pathname === "/api/auth/login" && r.request().method() === "POST",
  );
  await page.goto(`${frontendUrl}/login`);
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  const response = await pending;
  assert(response.status() === 200, "login_not_accepted");
  const body = await response.json();
  const token = body?.data?.accessToken;
  assert(typeof token === "string" && token.length > 0, "access_token_not_captured");
  await page.waitForURL("**/smart-water/**", { timeout: 15000 });
  // The auth context silently refreshes on mount (auth-context.tsx), and central
  // auth ROTATES the refresh cookie on every refresh. Wait for that first
  // refresh to COMPLETE before any further full-page navigation: a second
  // navigation whose mount-refresh races the still-in-flight first one on the
  // same rotating token permanently signs the session out (AuthGuard then
  // bounces to /login and the planning-depth reads never fire) — #165.
  await page
    .waitForResponse((r) => new URL(r.url()).pathname === AUTH_REFRESH_PATH, {
      timeout: 15000,
    })
    .catch(() => null);
  return token;
}

/** Render the planning-depth panel and report what the operator can actually
 * see. Absence of the Submit control is the product's own denial/outage
 * contract (PlanningRhsPanel.test.tsx:799 asserts exactly this). */
async function readPanelAffordance(page, frontendUrl) {
  // Arm the response waiters BEFORE navigating: the panel's policy is derived
  // from these two reads, so the DOM is only meaningful once they have settled.
  const rosterSettled = page
    .waitForResponse((r) => new URL(r.url()).pathname === ROSTER_PATH, {
      timeout: 30000,
    })
    .catch(() => null);
  const activeSettled = page
    .waitForResponse((r) => new URL(r.url()).pathname === ACTIVE_PATH, {
      timeout: 30000,
    })
    .catch(() => null);
  const response = await page.goto(`${frontendUrl}${WATER_PLANNING_PATH}`, {
    waitUntil: "domcontentloaded",
  });
  // A wrong route renders a 404 with no Submit control, which would otherwise be
  // recorded as "the affordance is correctly absent" -- a routing bug reported as
  // a passing denial proof.
  assert(response !== null && response.status() === 200, "water_planning_route_missing");
  // The recorder is injected with `new Function` so the unit-tested pure helper
  // is the code that actually runs (no second copy). smart-cms-app sets no CSP
  // today; if one were ever added with a strict `script-src`, that injection
  // would throw and this would otherwise surface as an opaque 35s timeout.
  const recorderInstalled = await page.evaluate(
    () => typeof window.__planningDepthReads === "object",
  );
  assert(recorderInstalled, "read_recorder_not_installed");

  const [rosterResponse, activeResponse] = await Promise.all([
    rosterSettled,
    activeSettled,
  ]);
  // Two independent conditions, neither sufficient alone:
  //   1. both reads reached the page AND their bodies arrived (the recorder),
  //      which is what makes the app's policy derivable at all; and
  //   2. two animation frames, so React/react-query have flushed it into the DOM.
  // (2) is a heuristic, not a guarantee -- which is why the banners are only
  // CORROBORATION here and the probative evidence is `panel_*_status` plus the
  // explicit 403/502 probes. The outage banner in particular is also what the
  // `not-requested` placeholder renders, so it can never carry the proof alone.
  await page.waitForFunction(
    (paths) =>
      paths.every(
        (pathname) =>
          window.__planningDepthReads &&
          window.__planningDepthReads[pathname] !== undefined,
      ),
    planningReadPaths(),
    { timeout: 35000 },
  );
  await page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
  const submitCount = await page
    .getByRole("button", { name: SUBMIT_BUTTON_NAME, exact: true })
    .count();
  const bodyText = await page.locator("body").innerText();
  return {
    submit_absent: submitCount === 0,
    denied_banner: bodyText.includes(DENIED_BANNER),
    unavailable_banner: bodyText.includes(UNAVAILABLE_BANNER),
    // Proof the policy was derived from REAL reads rather than the placeholder.
    panel_roster_status: rosterResponse ? rosterResponse.status() : null,
    panel_active_status: activeResponse ? activeResponse.status() : null,
  };
}

/** Probe both planning-depth reads explicitly and report their real statuses.
 *
 * The passive per-context observation is kept only as a cross-check: the app's
 * active query is `enabled: submitEnabled && weekKey !== null`, so during an
 * outage it can be disabled entirely and observe nothing -- which would fail the
 * drill for a reason unrelated to what it measures.
 */
async function probePlanningDepthReads(page, token, weekKey) {
  const roster = await planningDepthRead(page, token, ROSTER_PATH);
  const active = await planningDepthRead(
    page,
    token,
    `${ACTIVE_PATH}?project_key=mun-bon&week_key=${weekKey}`,
  );
  return { roster_status: roster.status, active_status: active.status };
}

/** Issue a request from the page using an init built HERE, in Node, by
 * `authorizedRequestInit`. Building it outside the page is what makes that
 * helper's unit test load-bearing: if the bearer stopped being attached, the
 * test would fail rather than the runtime silently 401-ing. */
async function fetchWithInit(page, url, init) {
  return page.evaluate(
    async ({ url, init }) => {
      try {
        const res = await fetch(url, init);
        let body = null;
        try {
          body = await res.json();
        } catch {
          body = null;
        }
        return { status: res.status, body };
      } catch (err) {
        // A request that never reached the server is NOT a status. Reporting 0
        // here would let "the fetch failed" be read as "the write was denied".
        return { status: null, transport_error: String(err && err.message), body: null };
      }
    },
    { url, init },
  );
}

function planningDepthSubmission({ weekKey, weekDate, activeId, base }) {
  return {
    schema_version: 2,
    project_key: "mun-bon",
    calendar_system: "rid-irrigation-v1",
    week_key: weekKey,
    week_date: weekDate,
    client_submission_id: crypto.randomUUID(),
    expected_active_submission_id: activeId,
    levels: Array.from({ length: 6 }, (_, i) => ({
      area_type: "zone",
      area_id: `01-${String(i + 1).padStart(2, "0")}`,
      planning_depth_mm: base + i * 10,
    })),
  };
}

async function planningDepthWrite(page, token, payload, submitPath) {
  return fetchWithInit(
    page,
    submitPath,
    authorizedRequestInit(token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
}

async function planningDepthRead(page, token, url) {
  return fetchWithInit(page, url, authorizedRequestInit(token, { method: "GET" }));
}

async function submitProbe(page, token, { weekKey, weekDate, submitPath }) {
  const response = await planningDepthWrite(
    page,
    token,
    planningDepthSubmission({ weekKey, weekDate, activeId: null, base: 250.0 }),
    submitPath,
  );
  return response.status;
}

async function logoutContext(context, frontendUrl) {
  const response = await context.request.post(`${frontendUrl}/api/auth/logout`);
  return response.status();
}

// The frontend re-wraps the central refreshToken VALUE into its own hardened
// cookie (smart-cms-app lib/auth/server.ts:5, hardenRefreshCookie) -- so this
// cookie's value IS the credential central auth revokes on logout.
const REFRESH_COOKIE_NAME = "smart_cms_refresh";
const AUTH_REFRESH_PATH = "/api/auth/refresh";
const AUTH_REFRESH_URL = "http://127.0.0.1:3005/api/v1/auth/refresh";

/** The strongest non-destructive control on a captured refresh credential:
 * central auth ROTATES (revokes + reissues) on every refresh, so probing
 * liveness would itself kill the token and make the post-logout 401 vacuous.
 * Shape-checking the raw JWT (payload.type === "refresh") instead catches the
 * real wrong-capture modes -- re-encoded/wrapped/percent-escaped values or the
 * wrong cookie entirely -- without consuming the credential. */
function assertRefreshShaped(value) {
  try {
    const segments = String(value).split(".");
    if (segments.length !== 3) throw new Error("segments");
    const payload = JSON.parse(Buffer.from(segments[1], "base64url").toString());
    if (payload.type !== "refresh") throw new Error("type");
    return value;
  } catch {
    throw new Error("refresh_cookie_not_refresh_shaped");
  }
}

/** THIS context's own refresh credential, captured BEFORE its logout -- the
 * revocation proof must concern the session the browser actually held, not a
 * separately created one (#160 HIGH-1). context.cookies() includes HttpOnly. */
async function contextRefreshCookie(context) {
  const matches = (await context.cookies()).filter(
    (candidate) => candidate.name === REFRESH_COOKIE_NAME && candidate.value,
  );
  if (matches.length === 0) throw new Error("refresh_cookie_not_captured");
  // Refuse to guess: two same-named cookies (different scope) could bind the
  // probe to a stale credential rather than the one logout revokes (#160).
  if (matches.length > 1) throw new Error("refresh_cookie_ambiguous");
  return assertRefreshShaped(matches[0].value);
}

/** Reuse the captured credential against central auth AFTER logout; only the
 * integer status is ever recorded (the sanitizer forbids token material).
 * express.json() only parses with the explicit JSON content type. */
async function refreshReuseStatus(refreshValue) {
  // Bounded: a wedged auth service must surface HERE (named checkpoint), not
  // as the outer 300s communicate timeout blaming the outage coordination.
  const response = await fetch(AUTH_REFRESH_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refreshToken: refreshValue }),
    signal: AbortSignal.timeout(15000),
  });
  return response.status;
}

/** The one logout-proof ordering for every context: capture THIS context's own
 * credential, log THIS context out, prove THAT captured value is now dead.
 * Extracted as a seam so the ordering is pinned by a node test rather than by
 * source-string inspection (#160 review). */
/** Revoke BOTH operator sessions even if one context's proof throws: a
 * capture/shape failure on the primary must not skip the second context's
 * logout (#160). Runs both proofs, then surfaces the first error. */
async function proveBothOperatorLogouts(
  primaryContext,
  secondContext,
  frontendUrl,
  deps = {},
) {
  const { prove = proveContextLogout } = deps;
  let primaryProof = null;
  let secondProof = null;
  let firstError = null;
  try {
    primaryProof = await prove(primaryContext, frontendUrl);
  } catch (error) {
    firstError = error;
  }
  try {
    secondProof = await prove(secondContext, frontendUrl);
  } catch (error) {
    firstError = firstError || error;
  }
  if (firstError) throw firstError;
  return { primaryProof, secondProof };
}

/** The failure code the subprocess emits for `checkpoint`. A code-shaped
 * (string) err.message surfaces directly so named diagnostics reach the
 * manifest; anything else — a hyphenated checkpoint, a non-Error throw, a
 * message with spaces — becomes `browser_<checkpoint>_failed` with hyphens
 * underscored so the Python extractor's [a-z0-9_] grammar accepts it. */
function browserFailureCode(err, checkpoint) {
  const message = err && typeof err.message === "string" ? err.message : "";
  if (/^[a-z][a-z0-9_]{0,127}$/.test(message)) return message;
  const safeCheckpoint = String(checkpoint).replace(/[^a-z0-9]+/g, "_");
  return `browser_${safeCheckpoint}_failed`;
}

async function proveContextLogout(context, frontendUrl, deps = {}) {
  const {
    capture = contextRefreshCookie,
    logout = logoutContext,
    probe = refreshReuseStatus,
  } = deps;
  // Capture may fail (renamed/reshaped cookie), but the logout POST is the
  // server-side session-revocation guarantee and must fire regardless (#160);
  // only surface the capture failure AFTER logging out.
  let refreshValue = null;
  let captureError = null;
  try {
    refreshValue = await capture(context);
  } catch (error) {
    captureError = error;
  }
  let logoutStatus;
  try {
    logoutStatus = await logout(context, frontendUrl);
  } catch (logoutError) {
    // A capture failure is the ROOT diagnosis (renamed/reshaped cookie); if the
    // mandatory logout ALSO fails, do not let the transport error bury it.
    throw captureError || logoutError;
  }
  if (captureError) throw captureError;
  const reuseStatus = await probe(refreshValue);
  return { logout_status: logoutStatus, refresh_reuse_status: reuseStatus };
}

/** Navigate to a protected page and report where the browser ACTUALLY ended up.
 *
 * The redirect is client-side (middleware.ts does not gate /smart-water), so a
 * bare goto races it -- but waiting for "/login" and then recording the URL
 * would make the recorded value "/login" by construction, which is the same
 * self-fulfilling evidence this stage exists to delete. So: wait, tolerate the
 * timeout, and report the real landing path either way. A session that was not
 * torn down reports the dashboard, and the validator rejects it.
 */
/** True for any request that leaves the local frontend origin.
 *
 * The planning workspace mounts a Leaflet map unconditionally
 * (WaterPlanningWorkspaceV2.tsx:134 -> WaterQualityMap), which fetches tiles and
 * marker icons from tile.openstreetmap.org, server.arcgisonline.com and
 * unpkg.com. None of them is relevant to anything this stage asserts, and an
 * acceptance gate that is loopback-pinned everywhere else must not depend on
 * three public hosts -- on an isolated guest they stall until timeout and abort
 * the drill before any evidence exists.
 */
function isOffOriginRequest(url, frontendOrigin) {
  try {
    // Normalize BOTH sides: the caller passes LOCAL_FRONTEND_URL verbatim, and a
    // trailing slash or path would otherwise make every request look off-origin
    // and abort 100% of traffic.
    return new URL(url).origin !== new URL(frontendOrigin).origin;
  } catch {
    return true;
  }
}

/** The reads whose completion makes the panel's policy terminal.
 *
 * Readiness cannot be a DOM signal. `draft-action-bar` renders from local draft
 * state before the queries are issued, and the "upstream unavailable" banner
 * renders from the `not-requested` PLACEHOLDER -- mutation-policy.ts:20 maps
 * every non-authorized/forbidden outcome to `unavailable`, ungated. Both are
 * therefore present from the first client render in every drill, so any
 * predicate accepting them resolves instantly and gates nothing.
 *
 * What actually makes the policy terminal is the app's OWN reads completing, so
 * that is what we wait for -- recorded in-page, then flushed through a render.
 */
function planningReadPaths() {
  return [ROSTER_PATH, ACTIVE_PATH];
}

/** Record one completed read into `reads`, keyed by pathname.
 *
 * Pure so it can be unit-tested: this is the whole of the observation mechanism,
 * and the defect it replaced was caught by a node test. Query strings are
 * ignored (the active read carries `?project_key=…&week_key=…`), off-path URLs
 * are skipped, and a malformed URL must never throw into the product's request.
 */
function recordPlanningRead(reads, url, status, paths, origin, bodySettled) {
  // Only an EXPLICIT true records (#160): an omitted or false flag means the
  // body never settled, and headers alone are not evidence the app read it.
  if (bodySettled !== true) return reads;
  try {
    const pathname = new URL(url, origin).pathname;
    if (paths.includes(pathname)) reads[pathname] = status;
  } catch {
    // Instrumentation must never break the page.
  }
  return reads;
}

/** The in-page fetch instrumentation, extracted so the SAME source that runs in
 * the browser (injected via toString, like recordPlanningRead) is the code the
 * node tests drive with an aborting body — no second copy. */
function makePlanningFetchWrapper({ originalFetch, reads, paths, origin, record }) {
  return async (...args) => {
    const response = await originalFetch(...args);
    // Record only once the BODY has arrived, not at headers-received: the app
    // cannot have derived its policy from a response it has not read. A clone
    // keeps the product's own stream untouched, and the path gate keeps the
    // instrumentation off every OTHER response the product makes. A body that
    // aborts after headers leaves the read UNRECORDED, so the settle waiter
    // times out instead of accepting headers as reads (#160).
    let bodySettled = true;
    try {
      const settled = new URL(response.url, origin).pathname;
      if (paths.includes(settled)) await response.clone().arrayBuffer();
    } catch {
      bodySettled = false;
    }
    record(reads, response.url, response.status, paths, origin, bodySettled);
    return response;
  };
}

/** Record the app's own planning-depth read completions inside the page.
 * Must be installed on the CONTEXT before any navigation; Playwright re-runs
 * init scripts on every navigation, which also resets the map per page load. */
function installReadRecorder(context) {
  return context.addInitScript(
    ({ paths, recordSource, wrapperSource }) => {
      // eslint-disable-next-line no-new-func
      const record = new Function(`return (${recordSource})`)();
      // eslint-disable-next-line no-new-func
      const makeWrapper = new Function(`return (${wrapperSource})`)();
      const reads = {};
      window.fetch = makeWrapper({
        originalFetch: window.fetch.bind(window),
        reads,
        paths,
        origin: window.location.origin,
        record,
      });
      // Sentinel LAST: readPanelAffordance's read_recorder_not_installed check
      // must fail if either injected source failed to rebuild in this realm --
      // a pre-set sentinel would report an unwrapped fetch as installed.
      window.__planningDepthReads = reads;
    },
    {
      paths: planningReadPaths(),
      recordSource: recordPlanningRead.toString(),
      wrapperSource: makePlanningFetchWrapper.toString(),
    },
  );
}

function installOriginBoundary(context, frontendOrigin) {
  return context.route("**/*", async (route) => {
    // Playwright leaves this handler's promise uncaught and rethrows on failure,
    // so a request still in flight when a context closes would become an
    // unhandled rejection and kill the process BEFORE the evidence is written --
    // losing a completed drill to a teardown race.
    try {
      if (isOffOriginRequest(route.request().url(), frontendOrigin)) {
        await route.abort("blockedbyclient");
        return;
      }
      await route.continue();
    } catch {
      // The context is closing; nothing left to route.
    }
  });
}

async function closeContext(context) {
  try {
    await context.unrouteAll({ behavior: "ignoreErrors" });
  } catch {
    // Older Playwright, or already closed.
  }
  await context.close();
}

function navigationSteps({ reload = false } = {}) {
  return reload ? ["goto", "reload"] : ["goto"];
}

async function landingPathAfter(page, frontendUrl, { reload = false } = {}) {
  // `commit` resolves as soon as the response arrives -- BEFORE hydration runs
  // the client-side redirect. Without it, a plain goto would already have landed
  // on /login and the reload below would merely reload /login, proving nothing.
  let reloadedFrom = null;
  for (const step of navigationSteps({ reload })) {
    if (step === "goto") {
      await page.goto(`${frontendUrl}${WATER_PLANNING_PATH}`, {
        waitUntil: reload ? "commit" : "load",
      });
    } else {
      // `commit` is a timing assumption, not a guarantee. Record what was
      // actually reloaded so a race that reloads /login degrades to a visibly
      // weaker proof instead of a silently self-fulfilling one.
      reloadedFrom = new URL(page.url()).pathname;
      await page.reload();
    }
  }
  try {
    await page.waitForURL((url) => new URL(url).pathname === "/login", {
      timeout: 15000,
    });
  } catch {
    // Fall through and record wherever it actually settled.
  }
  return { landing: new URL(page.url()).pathname, reloaded_from: reloadedFrom };
}

module.exports = {
  recordPlanningRead,
  makePlanningFetchWrapper,
  proveContextLogout,
  proveBothOperatorLogouts,
  browserFailureCode,
  assertRefreshShaped,
  contextRefreshCookie,
  isOffOriginRequest,
  planningReadPaths,
  navigationSteps,
  classifyProductRequest,
  isForbiddenWrite,
  authorizedRequestInit,
  validateControlPath,
};

if (require.main === module) {
  (async () => {
    const { chromium } = require("playwright");

    const frontendUrl = required("LOCAL_FRONTEND_URL");
    const email = required("MUNBON_OPERATOR_EMAIL");
    const password = required("MUNBON_OPERATOR_PASSWORD");
    const fieldTeamEmail = required("MUNBON_FIELD_TEAM_EMAIL");
    const fieldTeamPassword = required("MUNBON_FIELD_TEAM_PASSWORD");
    const weekKey = required("LOCAL_WEEK_KEY");
    const weekDate = required("LOCAL_WEEK_DATE");
    const readyPath = validateControlPath(
      required("LOCAL_WRITE_UI_READY_FILE"),
      ".write-ui-ready",
    );
    const releasePath = validateControlPath(
      required("LOCAL_WRITE_UI_OUTAGE_RELEASE_FILE"),
      ".write-ui-outage-release",
    );

    const inventory = {
      phase: "healthy",
      writeExpected: false,
      mutations: [],
      forbiddenWrites: [],
      observed: {
        healthy: { roster_status: null, active_status: null },
        outage: { roster_status: null, active_status: null },
        field_team: { roster_status: null, active_status: null },
      },
    };
    // Operator contexts follow the healthy -> outage lifecycle; the field-team
    // context always writes to its own bucket and can never be contaminated.
    const operatorBucket = () => inventory.observed[inventory.phase];
    const fieldTeamBucket = () => inventory.observed.field_team;
    const result = {};
    const browser = await chromium.launch({ headless: true });

    try {
      checkpoint = "primary-context";
      const primaryContext = await browser.newContext();
      installResponseBoundary(primaryContext, inventory, operatorBucket);
      await installOriginBoundary(primaryContext, frontendUrl);
      await installReadRecorder(primaryContext);
      const page = await primaryContext.newPage();

      checkpoint = "primary-login";
      const token = await loginAndCaptureToken(page, frontendUrl, email, password);

      checkpoint = "verify-submit-affordance";
      const healthyPanel = await readPanelAffordance(page, frontendUrl);
      assert(healthyPanel.submit_absent === false, "submit_affordance_not_visible");

      checkpoint = "create-submission";
      inventory.writeExpected = true;
      const createResponse = await planningDepthWrite(
        page,
        token,
        planningDepthSubmission({
          weekKey,
          weekDate,
          activeId: null,
          base: 250.0,
        }),
        SUBMIT_PATH,
      );
      assert(createResponse.status === 201, "create_not_201");

      // The submit receipt is reduced to {success, submissionId, submittedAt,
      // replayed} (route.ts:186-193) -- it carries NO client_submission_id, so
      // no client-id claim can be made from it.
      result.create_result = {
        status: createResponse.status,
        submission_id: createResponse.body.submissionId,
        replayed: createResponse.body.replayed,
      };

      checkpoint = "active-readback";
      const activeResponse = await planningDepthRead(
        page,
        token,
        `${ACTIVE_PATH}?project_key=mun-bon&week_key=${weekKey}`,
      );
      // The active proxy returns the BFF body VERBATIM (snake_case, 41 levels),
      // unlike the submit receipt which is reduced to camelCase. Mixing the two
      // conventions is the contract drift that made the merged stage vacuous.
      assert(activeResponse.status === 200, "active_readback_not_200");
      const activeLevels = Array.isArray(activeResponse.body.levels)
        ? activeResponse.body.levels
        : [];
      result.active_readback = {
        status: activeResponse.status,
        submission_id: activeResponse.body.submission_id,
        levels_count: activeLevels.length,
        // 41 rows alone cannot tell a correct zone->section fan-out from one that
        // served every section a single zone's depth.
        distinct_depths: [
          ...new Set(activeLevels.map((level) => Number(level.planning_depth_mm))),
        ].sort((a, b) => a - b),
      };

      checkpoint = "second-context";
      const secondContext = await browser.newContext();
      installResponseBoundary(secondContext, inventory, operatorBucket);
      await installOriginBoundary(secondContext, frontendUrl);
      await installReadRecorder(secondContext);
      const page2 = await secondContext.newPage();
      const token2 = await loginAndCaptureToken(
        page2,
        frontendUrl,
        email,
        password,
      );

      checkpoint = "correct-submission";
      const correctResponse = await planningDepthWrite(
        page2,
        token2,
        planningDepthSubmission({
          weekKey,
          weekDate,
          activeId: result.active_readback.submission_id,
          base: 260.0,
        }),
        SUBMIT_PATH,
      );
      assert(correctResponse.status === 201, "correct_not_201");
      result.correct_result = {
        status: correctResponse.status,
        submission_id: correctResponse.body.submissionId,
      };

      checkpoint = "stale-conflict";
      const conflictResponse = await planningDepthWrite(
        page,
        token,
        planningDepthSubmission({
          weekKey,
          weekDate,
          activeId: result.create_result.submission_id,
          base: 270.0,
        }),
        SUBMIT_PATH,
      );
      assert(conflictResponse.status === 409, "conflict_not_409");
      result.conflict_result = { status: conflictResponse.status };

      checkpoint = "conflict-reconciliation";
      const reconcileResponse = await planningDepthRead(
        page,
        token,
        `${ACTIVE_PATH}?project_key=mun-bon&week_key=${weekKey}`,
      );
      assert(reconcileResponse.status === 200, "reconciliation_not_200");
      result.conflict_reconciliation = {
        status: reconcileResponse.status,
        submission_id: reconcileResponse.body.submission_id,
      };

      inventory.writeExpected = false;

      checkpoint = "field-team-context";
      const fieldTeamContext = await browser.newContext();
      installResponseBoundary(fieldTeamContext, inventory, fieldTeamBucket);
      await installOriginBoundary(fieldTeamContext, frontendUrl);
      await installReadRecorder(fieldTeamContext);
      const fieldPage = await fieldTeamContext.newPage();
      const fieldToken = await loginAndCaptureToken(
        fieldPage,
        frontendUrl,
        fieldTeamEmail,
        fieldTeamPassword,
      );
      const fieldPanel = await readPanelAffordance(fieldPage, frontendUrl);
      const fieldPassiveRoster = inventory.observed.field_team.roster_status;
      const fieldReads = await probePlanningDepthReads(fieldPage, fieldToken, weekKey);
      const fieldSubmitStatus = await submitProbe(fieldPage, fieldToken, {
        weekKey,
        weekDate,
        submitPath: SUBMIT_PATH,
      });
      const fieldLogoutProof = await proveContextLogout(
        fieldTeamContext,
        frontendUrl,
      );
      result.field_team_result = {
        roster_status: fieldReads.roster_status,
        active_status: fieldReads.active_status,
        observed_roster_status: fieldPassiveRoster,
        submit_absent: fieldPanel.submit_absent,
        denied_banner: fieldPanel.denied_banner,
        unavailable_banner: fieldPanel.unavailable_banner,
        panel_roster_status: fieldPanel.panel_roster_status,
        panel_active_status: fieldPanel.panel_active_status,
        submit_status: fieldSubmitStatus,
        logout_status: fieldLogoutProof.logout_status,
        refresh_reuse_status: fieldLogoutProof.refresh_reuse_status,
      };
      await closeContext(fieldTeamContext);

      checkpoint = "outage-coordination";
      inventory.phase = "outage";
      fs.writeFileSync(readyPath, "ready\n");
      await waitForControlFile(releasePath, 180000);

      // The release means the scheduler is now DOWN. Discard anything observed
      // while it was still up, so only genuinely-during-outage reads count.
      inventory.observed.outage.roster_status = null;
      inventory.observed.outage.active_status = null;

      checkpoint = "outage-probe";
      const outagePanel = await readPanelAffordance(page, frontendUrl);
      const outagePassiveRoster = inventory.observed.outage.roster_status;
      const outageReads = await probePlanningDepthReads(page, token, weekKey);
      const outageSubmitStatus = await submitProbe(page, token, {
        weekKey,
        weekDate,
        submitPath: SUBMIT_PATH,
      });
      result.outage_result = {
        roster_status: outageReads.roster_status,
        active_status: outageReads.active_status,
        observed_roster_status: outagePassiveRoster,
        submit_absent: outagePanel.submit_absent,
        unavailable_banner: outagePanel.unavailable_banner,
        denied_banner: outagePanel.denied_banner,
        panel_roster_status: outagePanel.panel_roster_status,
        panel_active_status: outagePanel.panel_active_status,
        submit_status: outageSubmitStatus,
      };

      checkpoint = "logout";
      // Both operator sessions must be revoked; a proof failure on one context
      // must not skip the other's logout POST.
      const { primaryProof, secondProof } = await proveBothOperatorLogouts(
        primaryContext,
        secondContext,
        frontendUrl,
      );
      result.logout_result = {
        status: primaryProof.logout_status,
        second_context_status: secondProof.logout_status,
        refresh_reuse_status: primaryProof.refresh_reuse_status,
        second_context_refresh_reuse_status: secondProof.refresh_reuse_status,
        redirect_url: (await landingPathAfter(page, frontendUrl)).landing,
      };

      checkpoint = "reload-after-logout";
      const reloadOutcome = await landingPathAfter(page, frontendUrl, {
        reload: true,
      });
      result.reload_result = {
        redirect_url: reloadOutcome.landing,
        reloaded_from: reloadOutcome.reloaded_from,
      };

      await closeContext(secondContext);
      await closeContext(primaryContext);

      result.request_inventory = {
        forbidden_write_count: inventory.forbiddenWrites.length,
        forbidden_writes: inventory.forbiddenWrites,
        total_mutations: inventory.mutations.length,
      };
    } catch (err) {
      // A clean, extractor-valid code token (see browserFailureCode); the human
      // detail rides on a separate, non-extracted line.
      const failureCode = browserFailureCode(err, checkpoint);
      const detail = err && err.message ? err.message : String(err);
      process.stderr.write(`FAIL write_browser: ${failureCode}\n`);
      if (failureCode !== detail) {
        process.stderr.write(`write_browser detail: ${detail}\n`);
      }
      await browser.close();
      process.exit(1);
    }

    await browser.close();
    process.stdout.write(JSON.stringify(result));
  })();
}
