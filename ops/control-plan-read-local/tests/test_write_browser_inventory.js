"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const {
  recordPlanningRead,
  makePlanningFetchWrapper,
  provePageOriginLogout,
  proveBothOperatorLogouts,
  pageOriginLogout,
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
  writeControlFile,
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

test("validateControlPath binds diagnostic coordination files to their evidence root", () => {
  const diagnosticRoot =
    "/var/lib/munbon-local-acceptance/write-ui-diagnostic";
  assert.equal(
    validateControlPath(
      `${diagnosticRoot}/.write-ui-ready`,
      ".write-ui-ready",
      diagnosticRoot,
    ),
    `${diagnosticRoot}/.write-ui-ready`,
  );
  assert.throws(
    () =>
      validateControlPath(
        "/var/lib/munbon-local-acceptance/evidence/.write-ui-ready",
        ".write-ui-ready",
        diagnosticRoot,
      ),
    /coordination_path_invalid/,
  );
});

test("writeControlFile refuses to follow an existing coordination symlink", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "write-ui-control-"));
  try {
    const victim = path.join(root, "victim");
    const target = path.join(root, ".write-ui-ready");
    fs.writeFileSync(victim, "unchanged\n");
    fs.symlinkSync(victim, target);

    assert.throws(() => writeControlFile(target, "ready\n"), /EEXIST/);
    assert.equal(fs.readFileSync(victim, "utf8"), "unchanged\n");
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
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
    true,
  );
  recordPlanningRead(reads, `${ORIGIN}${ROSTER_PATH}`, 502, [ROSTER_PATH, ACTIVE_PATH], ORIGIN, true);
  assert.deepEqual(reads, { [ACTIVE_PATH]: 502, [ROSTER_PATH]: 502 });

  // Off-path traffic (including the harness's own auth calls) must not register.
  recordPlanningRead(reads, `${ORIGIN}/api/auth/login`, 200, [ROSTER_PATH, ACTIVE_PATH], ORIGIN, true);
  recordPlanningRead(reads, `${ORIGIN}/_next/static/x.js`, 200, [ROSTER_PATH, ACTIVE_PATH], ORIGIN, true);
  assert.deepEqual(Object.keys(reads).sort(), [ACTIVE_PATH, ROSTER_PATH].sort());

  // A relative URL resolves against the page origin.
  const relative = {};
  recordPlanningRead(relative, ROSTER_PATH, 403, [ROSTER_PATH], ORIGIN, true);
  assert.deepEqual(relative, { [ROSTER_PATH]: 403 });
});

test("recordPlanningRead refuses to record a read whose body never settled", () => {
  // #160 MEDIUM: recording on headers alone lets a truncated body satisfy the
  // settle predicate. Anything but an explicit true means NOT settled.
  const reads = {};
  recordPlanningRead(reads, `${ORIGIN}${ROSTER_PATH}`, 502, [ROSTER_PATH], ORIGIN, false);
  recordPlanningRead(reads, `${ORIGIN}${ROSTER_PATH}`, 502, [ROSTER_PATH], ORIGIN, undefined);
  assert.deepEqual(reads, {});
});

test("recordPlanningRead never throws into the product's own request", () => {
  const reads = {};
  assert.doesNotThrow(() =>
    recordPlanningRead(reads, "::not a url::", 200, [ROSTER_PATH], undefined, true),
  );
  assert.deepEqual(reads, {});
});

function fakeResponse({ url, status, bodyRejects }) {
  return {
    url,
    status,
    clone() {
      return {
        arrayBuffer: () =>
          bodyRejects
            ? Promise.reject(new Error("body aborted after headers"))
            : Promise.resolve(new ArrayBuffer(0)),
      };
    },
  };
}

test("planning fetch wrapper records an on-path read only after its body settles", async () => {
  const reads = {};
  let releaseBody;
  const bodyGate = new Promise((resolve) => {
    releaseBody = resolve;
  });
  const wrapper = makePlanningFetchWrapper({
    originalFetch: async () => ({
      url: `${ORIGIN}${ROSTER_PATH}`,
      status: 200,
      clone() {
        return { arrayBuffer: () => bodyGate };
      },
    }),
    reads,
    paths: [ROSTER_PATH, ACTIVE_PATH],
    origin: ORIGIN,
    record: recordPlanningRead,
  });
  const pending = wrapper(`${ORIGIN}${ROSTER_PATH}`);
  await new Promise((resolve) => setImmediate(resolve));
  // Recording at headers-received is exactly the #160 fail-open this pins.
  assert.deepEqual(reads, {});
  releaseBody(new ArrayBuffer(0));
  const response = await pending;
  assert.equal(response.status, 200);
  assert.deepEqual(reads, { [ROSTER_PATH]: 200 });
});

test("provePageOriginLogout captures before its page logout and probes that value", async () => {
  // #160 HIGH-1's load-bearing ordering, as behavior rather than source strings:
  // the revocation probe must receive the SAME context's pre-logout credential.
  const events = [];
  const fakeContext = { label: "ctx-a" };
  const fakePage = { label: "page-a" };
  const accessToken = "access-of-ctx-a";
  const proof = await provePageOriginLogout(
    fakeContext,
    fakePage,
    accessToken,
    {
      capture: async (context) => {
        events.push(`capture:${context.label}`);
        return "credential-of-ctx-a";
      },
      logout: async (page, token) => {
        events.push(`logout:${page.label}:${token}`);
        return 204;
      },
      probe: async (value) => {
        events.push(`probe:${value}`);
        return 401;
      },
    },
  );
  assert.deepEqual(events, [
    "capture:ctx-a",
    "logout:page-a:access-of-ctx-a",
    "probe:credential-of-ctx-a",
  ]);
  assert.deepEqual(proof, { logout_status: 204, refresh_reuse_status: 401 });
});

test("pageOriginLogout uses a relative same-origin credentialed POST", async () => {
  const requests = [];
  const accessToken = "primary-access-token";
  const page = {
    evaluate: async (callback, argument) => {
      const originalFetch = globalThis.fetch;
      globalThis.fetch = async (url, init) => {
        requests.push({ url, init });
        return { status: 204 };
      };
      try {
        return await callback(argument);
      } finally {
        globalThis.fetch = originalFetch;
      }
    },
  };

  assert.equal(await pageOriginLogout(page, accessToken), 204);
  assert.deepEqual(requests, [
    {
      url: "/api/auth/logout",
      init: {
        method: "POST",
        credentials: "same-origin",
        headers: { Authorization: `Bearer ${accessToken}` },
      },
    },
  ]);
});

test("proveBothOperatorLogouts attempts both pages when the primary proof throws", async () => {
  const loggedOut = [];
  const prove = async (context, page, accessToken) => {
    loggedOut.push(`${context.label}:${page.label}:${accessToken}`);
    if (context.label === "primary")
      throw new Error("refresh_cookie_ambiguous");
    return { logout_status: 204, refresh_reuse_status: 401 };
  };
  await assert.rejects(
    () =>
      proveBothOperatorLogouts(
        {
          context: { label: "primary" },
          page: { label: "page-primary" },
          accessToken: "token-primary",
        },
        {
          context: { label: "second" },
          page: { label: "page-second" },
          accessToken: "token-second",
        },
        { prove },
      ),
    /refresh_cookie_ambiguous/,
  );
  assert.deepEqual(loggedOut, [
    "primary:page-primary:token-primary",
    "second:page-second:token-second",
  ]);
});

test("page-origin proofs use field and each operator's own page and bearer", async () => {
  const proofs = [];
  const fieldProof = await provePageOriginLogout(
    { label: "field" },
    { label: "page-field" },
    "token-field",
    {
      capture: async (context) => {
        proofs.push(`capture:${context.label}`);
        return "refresh-field";
      },
      logout: async (page, accessToken) => {
        proofs.push(`logout:${page.label}:${accessToken}`);
        return 200;
      },
      probe: async (refreshCredential) => {
        proofs.push(`probe:${refreshCredential}`);
        return 401;
      },
    },
  );
  const proof = await proveBothOperatorLogouts(
    {
      context: { label: "primary" },
      page: { label: "page-primary" },
      accessToken: "token-primary",
    },
    {
      context: { label: "second" },
      page: { label: "page-second" },
      accessToken: "token-second",
    },
    {
      prove: async (context, page, accessToken) => {
        proofs.push(`${context.label}:${page.label}:${accessToken}`);
        return { logout_status: 200, refresh_reuse_status: 401 };
      },
    },
  );

  assert.deepEqual(proofs, [
    "capture:field",
    "logout:page-field:token-field",
    "probe:refresh-field",
    "primary:page-primary:token-primary",
    "second:page-second:token-second",
  ]);
  assert.deepEqual(fieldProof, {
    logout_status: 200,
    refresh_reuse_status: 401,
  });
  assert.deepEqual(proof, {
    primaryProof: { logout_status: 200, refresh_reuse_status: 401 },
    secondProof: { logout_status: 200, refresh_reuse_status: 401 },
  });
});

test("browserFailureCode surfaces a code-shaped message and sanitizes hyphenated checkpoints", () => {
  assert.equal(
    browserFailureCode(new Error("refresh_cookie_ambiguous"), "logout"),
    "refresh_cookie_ambiguous",
  );
  assert.equal(
    browserFailureCode(new Error("net::ERR_RESET"), "create-submission"),
    "browser_create_submission_failed",
  );
  assert.equal(
    browserFailureCode("a bare string", "outage-probe"),
    "browser_outage_probe_failed",
  );
  assert.equal(
    browserFailureCode(undefined, "reload-after-logout"),
    "browser_reload_after_logout_failed",
  );
  for (const cp of ["create-submission", "field-team-context", "reload-after-logout"]) {
    assert.match(browserFailureCode(new Error("x y"), cp), /^[a-z][a-z0-9_]{0,127}$/);
  }
});

test("provePageOriginLogout surfaces the capture error when page logout also throws", async () => {
  // The renamed/reshaped-cookie diagnosis is the root cause; a logout transport
  // error under the same regression must not bury it (#160 round-3 review).
  await assert.rejects(
    provePageOriginLogout({ label: "ctx-c" }, { label: "page-c" }, "token-c", {
      capture: async () => {
        throw new Error("refresh_cookie_not_captured");
      },
      logout: async () => {
        throw new Error("browser_logout_transport_reset");
      },
      probe: async () => 401,
    }),
    /refresh_cookie_not_captured/,
  );
});

test("provePageOriginLogout still uses the page when capture fails", async () => {
  // A capture/shape failure must not leave the session live server-side: the
  // logout POST is the cleanup guarantee and must fire regardless (#160 review).
  const events = [];
  await assert.rejects(
    provePageOriginLogout({ label: "ctx-b" }, { label: "page-b" }, "token-b", {
      capture: async () => {
        throw new Error("refresh_cookie_not_captured");
      },
      logout: async (page, accessToken) => {
        events.push(`logout:${page.label}:${accessToken}`);
        return 204;
      },
      probe: async () => {
        events.push("probe");
        return 401;
      },
    }),
    /refresh_cookie_not_captured/,
  );
  // logout happened; probe did not (no captured credential to reuse).
  assert.deepEqual(events, ["logout:page-b:token-b"]);
});

test("planning fetch wrapper does NOT record an on-path read whose body aborts after headers", async () => {
  // #160 MEDIUM: the app cannot have derived policy from a body it never got.
  // Leaving the read unrecorded keeps the settle waiter waiting, so the drill
  // fails closed on its existing timeout instead of reporting headers as reads.
  const reads = {};
  const wrapper = makePlanningFetchWrapper({
    originalFetch: async () =>
      fakeResponse({ url: `${ORIGIN}${ROSTER_PATH}`, status: 502, bodyRejects: true }),
    reads,
    paths: [ROSTER_PATH, ACTIVE_PATH],
    origin: ORIGIN,
    record: recordPlanningRead,
  });
  const response = await wrapper(`${ORIGIN}${ROSTER_PATH}`);
  assert.equal(response.status, 502);
  assert.deepEqual(reads, {});
});

test("planning fetch wrapper never touches an off-path response body", async () => {
  // The paths gate must run BEFORE the clone: instrumentation reading every
  // response body would perturb the product's own request handling.
  const reads = {};
  let cloneCalls = 0;
  const wrapper = makePlanningFetchWrapper({
    originalFetch: async () => ({
      url: `${ORIGIN}/api/auth/login`,
      status: 200,
      clone() {
        cloneCalls += 1;
        return { arrayBuffer: () => Promise.reject(new Error("must not run")) };
      },
    }),
    reads,
    paths: [ROSTER_PATH, ACTIVE_PATH],
    origin: ORIGIN,
    record: recordPlanningRead,
  });
  const response = await wrapper(`${ORIGIN}/api/auth/login`);
  assert.equal(response.status, 200);
  assert.equal(cloneCalls, 0);
  assert.deepEqual(reads, {});
});

function jwtLike(payload) {
  const middle = Buffer.from(JSON.stringify(payload)).toString("base64url");
  return `header.${middle}.signature`;
}

function refreshJwt(sub) {
  const middle = Buffer.from(
    JSON.stringify({ type: "refresh", sub }),
  ).toString("base64url");
  return `header.${middle}.signature`;
}

test("contextRefreshCookie returns the single shaped smart_cms_refresh cookie", async () => {
  const value = refreshJwt("user-1");
  const context = {
    cookies: async () => [
      { name: "other", value: "x" },
      { name: "smart_cms_refresh", value },
    ],
  };
  assert.equal(await contextRefreshCookie(context), value);
});

test("contextRefreshCookie rejects ambiguous duplicate refresh cookies", async () => {
  const context = {
    cookies: async () => [
      { name: "smart_cms_refresh", value: refreshJwt("user-1") },
      { name: "smart_cms_refresh", value: refreshJwt("user-2") },
    ],
  };
  await assert.rejects(
    () => contextRefreshCookie(context),
    /refresh_cookie_ambiguous/,
  );
});

test("contextRefreshCookie rejects when no refresh cookie exists", async () => {
  const context = { cookies: async () => [{ name: "other", value: "x" }] };
  await assert.rejects(
    () => contextRefreshCookie(context),
    /refresh_cookie_not_captured/,
  );
});

test("assertRefreshShaped accepts a refresh-type JWT and rejects lookalikes", () => {
  const good = jwtLike({ type: "refresh", sub: "user-1" });
  assert.equal(assertRefreshShaped(good), good);
  // The failure modes a wrongly-captured cookie value actually takes:
  for (const bad of [
    jwtLike({ type: "access", sub: "user-1" }),
    // a re-encoded wrapper (e.g. the frontend base64-wrapping the JWT):
    Buffer.from(jwtLike({ type: "refresh", sub: "user-1" })).toString("base64"),
    "opaque-session-blob",
    "a.b",
    "",
  ]) {
    assert.throws(
      () => assertRefreshShaped(bad),
      /refresh_cookie_not_refresh_shaped/,
    );
  }
});

test("injected sources survive the new Function round-trip out of module scope", async () => {
  // The init script rebuilds these from source in the PAGE realm, where module
  // constants do not exist — a future edit capturing one would pass every
  // direct-call test and fail only as an opaque 35s in-page timeout.
  // eslint-disable-next-line no-new-func
  const rebuiltRecord = new Function(`return (${recordPlanningRead.toString()})`)();
  // eslint-disable-next-line no-new-func
  const rebuiltMakeWrapper = new Function(
    `return (${makePlanningFetchWrapper.toString()})`,
  )();
  const reads = {};
  const wrapper = rebuiltMakeWrapper({
    originalFetch: async () =>
      fakeResponse({ url: `${ORIGIN}${ROSTER_PATH}`, status: 200, bodyRejects: false }),
    reads,
    paths: [ROSTER_PATH, ACTIVE_PATH],
    origin: ORIGIN,
    record: rebuiltRecord,
  });
  const response = await wrapper(`${ORIGIN}${ROSTER_PATH}`);
  assert.equal(response.status, 200);
  assert.deepEqual(reads, { [ROSTER_PATH]: 200 });
});
