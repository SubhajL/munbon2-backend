"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const {
  recordPlanningRead,
  isOffOriginRequest,
  planningReadPaths,
  navigationSteps,
  classifyProductRequest,
  isForbiddenWrite,
  authorizedRequestInit,
  validateControlPath,
} = require("../run-write-browser.js");

const ORIGIN = "http://127.0.0.1:9999";
const SUBMIT_PATH =
  "/api/smart-water-backend/water-planning/planning-depth-submissions";
const ACTIVE_PATH =
  "/api/smart-water-backend/water-planning/planning-depth-submissions/active";
const ROSTER_PATH =
  "/api/smart-water-backend/water-planning/planning-depth-roster";
const DENIED_BANNER_TAIL = "บัญชีของคุณไม่มีสิทธิ์ในการส่งแผนระดับน้ำ";
const UNAVAILABLE_BANNER_TAIL = "ไม่สามารถตรวจสอบสิทธิ์การส่งได้ในขณะนี้";

test("classifyProductRequest labels each product request by kind", () => {
  assert.equal(classifyProductRequest(`${ORIGIN}/api/auth/login`, "POST"), "auth");
  assert.equal(classifyProductRequest(`${ORIGIN}/api/auth/logout`, "POST"), "auth");
  assert.equal(
    classifyProductRequest(`${ORIGIN}/_next/static/chunks/app.js`, "GET"),
    "framework",
  );
  assert.equal(classifyProductRequest(`${ORIGIN}/login`, "GET"), "document");
  assert.equal(
    classifyProductRequest(`${ORIGIN}/smart-water/dashboard/water-planning`, "GET"),
    "document",
  );
  assert.equal(classifyProductRequest(`${ORIGIN}${SUBMIT_PATH}`, "POST"), "mutation");
  assert.equal(classifyProductRequest(`${ORIGIN}${SUBMIT_PATH}`, "PUT"), "mutation");
  assert.equal(classifyProductRequest(`${ORIGIN}${ACTIVE_PATH}`, "GET"), "read");
  assert.equal(classifyProductRequest(`${ORIGIN}${ROSTER_PATH}`, "GET"), "read");
  assert.equal(classifyProductRequest(`${ORIGIN}/api/other/thing`, "GET"), "other");
});

test("isForbiddenWrite ignores the harness's own auth traffic", () => {
  // The boundary runs on EVERY response, and the harness logs in three times.
  // If login counted as a product write, forbiddenWrites would never be empty
  // and the stage could never pass -- while every offline test still went green.
  for (const writeExpected of [true, false]) {
    assert.equal(
      isForbiddenWrite({
        method: "POST",
        pathname: "/api/auth/login",
        status: 200,
        writeExpected,
      }),
      false,
    );
    assert.equal(
      isForbiddenWrite({
        method: "POST",
        pathname: "/api/auth/logout",
        status: 200,
        writeExpected,
      }),
      false,
    );
  }
  // A successful write to a NON-product path is still not a product write.
  assert.equal(
    isForbiddenWrite({
      method: "POST",
      pathname: "/api/telemetry",
      status: 200,
      writeExpected: false,
    }),
    false,
  );
});

test("isForbiddenWrite fires ONLY on a successful write when none was expected", () => {
  // The operator's intended writes during the write phase are expected → allowed.
  assert.equal(
    isForbiddenWrite({
      method: "POST",
      pathname: SUBMIT_PATH,
      status: 201,
      writeExpected: true,
    }),
    false,
  );
  // A field-team submit probe is a real 403 (no write) → not forbidden.
  assert.equal(
    isForbiddenWrite({
      method: "POST",
      pathname: SUBMIT_PATH,
      status: 403,
      writeExpected: false,
    }),
    false,
  );
  // An outage submit probe is a real 502 (no write) → not forbidden.
  assert.equal(
    isForbiddenWrite({
      method: "POST",
      pathname: SUBMIT_PATH,
      status: 502,
      writeExpected: false,
    }),
    false,
  );
  // A stale-conflict 409 during the write phase is not a successful write.
  assert.equal(
    isForbiddenWrite({
      method: "POST",
      pathname: SUBMIT_PATH,
      status: 409,
      writeExpected: true,
    }),
    false,
  );
  // A GET is never a write.
  assert.equal(
    isForbiddenWrite({
      method: "GET",
      pathname: ACTIVE_PATH,
      status: 200,
      writeExpected: false,
    }),
    false,
  );
  // THE defect the invariant guards: a 2xx write when none was expected.
  assert.equal(
    isForbiddenWrite({
      method: "POST",
      pathname: SUBMIT_PATH,
      status: 201,
      writeExpected: false,
    }),
    true,
  );
  assert.equal(
    isForbiddenWrite({
      method: "PUT",
      pathname: SUBMIT_PATH,
      status: 200,
      writeExpected: false,
    }),
    true,
  );
});

test("authorizedRequestInit attaches the captured bearer without mutating the caller init", () => {
  const init = { method: "POST", headers: { "Content-Type": "application/json" } };
  const out = authorizedRequestInit("tok-123", init);
  assert.equal(out.headers.Authorization, "Bearer tok-123");
  assert.equal(out.headers["Content-Type"], "application/json");
  assert.equal(out.method, "POST");
  // Must not have mutated the caller's object (no bearer leaked back).
  assert.equal("Authorization" in init.headers, false);
});

test("authorizedRequestInit refuses to build an unauthenticated request", () => {
  assert.throws(() => authorizedRequestInit("", { headers: {} }), /missing_bearer/);
  assert.throws(() => authorizedRequestInit(null, { headers: {} }), /missing_bearer/);
});

test("validateControlPath accepts only the named hidden file in the evidence root", () => {
  const root = "/var/lib/munbon-local-acceptance/evidence";
  assert.equal(
    validateControlPath(`${root}/.write-ui-ready`, ".write-ui-ready"),
    `${root}/.write-ui-ready`,
  );
  assert.throws(
    () => validateControlPath("/tmp/.write-ui-ready", ".write-ui-ready"),
    /coordination_path_invalid/,
  );
  assert.throws(
    () => validateControlPath(`${root}/.write-ui-ready`, ".write-ui-outage-release"),
    /coordination_path_invalid/,
  );
});

test("navigationSteps performs a real reload only when asked", () => {
  // A source-substring check for "page.reload(" survives a revert that leaves the
  // docstring intact, so the reload behaviour is driven by this pure function and
  // asserted here instead.
  assert.deepEqual(navigationSteps({ reload: false }), ["goto"]);
  assert.deepEqual(navigationSteps({}), ["goto"]);
  assert.deepEqual(navigationSteps({ reload: true }), ["goto", "reload"]);
});

test("isOffOriginRequest blocks every third-party asset the dashboard pulls", () => {
  // The planning workspace mounts a Leaflet map unconditionally, which fetches
  // tiles and marker icons from three public hosts. An acceptance stage that is
  // loopback-pinned everywhere else must not silently depend on them -- on an
  // isolated guest they stall until timeout and abort the drill before any
  // evidence exists.
  for (const external of [
    "https://a.tile.openstreetmap.org/10/1/2.png",
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/1/2/3",
    "https://unpkg.com/leaflet@1.7.1/dist/images/marker-icon.png",
  ]) {
    assert.equal(isOffOriginRequest(external, ORIGIN), true);
  }
  // Same-origin product traffic must never be blocked.
  for (const local of [
    `${ORIGIN}/smart-water/dashboard`,
    `${ORIGIN}${SUBMIT_PATH}`,
    `${ORIGIN}/api/auth/login`,
    `${ORIGIN}/_next/static/chunks/app.js`,
  ]) {
    assert.equal(isOffOriginRequest(local, ORIGIN), false);
  }
});

test("planningReadPaths returns exactly the two planning-depth pathnames", () => {
  // The unavailable banner renders from the `not-requested` PLACEHOLDER
  // (mutation-policy.ts:20 maps every non-authorized/forbidden outcome to
  // `unavailable`, and PlanningRhsPanel.tsx:520 does not gate it on
  // submitEnabled). It is therefore present from the FIRST client render in
  // every drill, and can never be a readiness signal -- a settle predicate that
  // accepts it resolves immediately and gates nothing, letting the outage drill
  // pass having asked nothing.
  const paths = planningReadPaths();

  assert.deepEqual(paths, [ROSTER_PATH, ACTIVE_PATH]);
});

test("recordPlanningRead keys planning reads by pathname and ignores everything else", () => {
  // This is the WHOLE observation mechanism. The defect it replaced was caught by
  // a node test; without this one, a regression here surfaces only as a 20s
  // timeout on a real guest.
  const reads = {};

  // Query strings must not defeat the match -- the active read always carries them.
  recordPlanningRead(
    reads,
    `${ORIGIN}${ACTIVE_PATH}?project_key=mun-bon&week_key=2027-R01`,
    502,
    [ROSTER_PATH, ACTIVE_PATH],
    ORIGIN,
  );
  recordPlanningRead(reads, `${ORIGIN}${ROSTER_PATH}`, 502, [ROSTER_PATH, ACTIVE_PATH], ORIGIN);
  assert.deepEqual(reads, { [ACTIVE_PATH]: 502, [ROSTER_PATH]: 502 });

  // Off-path traffic (including the harness's own auth calls) must not register.
  recordPlanningRead(reads, `${ORIGIN}/api/auth/login`, 200, [ROSTER_PATH, ACTIVE_PATH], ORIGIN);
  recordPlanningRead(reads, `${ORIGIN}/_next/static/x.js`, 200, [ROSTER_PATH, ACTIVE_PATH], ORIGIN);
  assert.deepEqual(Object.keys(reads).sort(), [ACTIVE_PATH, ROSTER_PATH].sort());

  // A relative URL resolves against the page origin.
  const relative = {};
  recordPlanningRead(relative, ROSTER_PATH, 403, [ROSTER_PATH], ORIGIN);
  assert.deepEqual(relative, { [ROSTER_PATH]: 403 });
});

test("recordPlanningRead never throws into the product's own request", () => {
  const reads = {};
  assert.doesNotThrow(() =>
    recordPlanningRead(reads, "::not a url::", 200, [ROSTER_PATH], undefined),
  );
  assert.deepEqual(reads, {});
});
