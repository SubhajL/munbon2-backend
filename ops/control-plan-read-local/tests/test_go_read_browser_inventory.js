"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const {
  classifyGateRequest,
  login,
  validateControlPath,
} = require("../run-go-read-browser.js");

const frontendOrigin = "http://127.0.0.1:9998";
const scadaOrigin = "http://127.0.0.1:3030";
const livePath = "/api/read-only/gates/waste-way/status";
const unknownPath = "/api/read-only/gates/unknown-gate/status";
const allowedStatusPaths = new Set([livePath, unknownPath]);
const gatePath = "/read-only/gates/waste-way";
const unknownGatePath = "/read-only/gates/unknown-gate";
const allowedDocumentPaths = new Set(["/login", gatePath, unknownGatePath]);

function classify(path, method = "GET", origin = frontendOrigin) {
  return classifyGateRequest({
    url: `${origin}${path}`,
    method,
    frontendOrigin,
    scadaOrigin,
    allowedStatusPaths,
    allowedDocumentPaths,
  });
}

test("allows only exact auth, status, document, and static asset requests", () => {
  assert.equal(classify("/api/auth/login", "POST").allowed, true);
  assert.equal(classify("/api/auth/refresh", "POST").allowed, true);
  assert.equal(classify("/api/auth/logout", "POST").allowed, true);
  assert.equal(classify(livePath).allowed, true);
  assert.equal(classify(unknownPath).allowed, true);
  assert.equal(classify(gatePath).allowed, true);
  assert.equal(classify(`${gatePath}?_rsc=abc123`).allowed, true);
  assert.equal(
    classify(`/login?next=${encodeURIComponent(gatePath)}`).allowed,
    true,
  );
  assert.equal(classify("/_next/static/chunks/app.js").allowed, true);
  assert.equal(classify("/?_rsc=backLinkPrefetch").allowed, true);
});

test("blocks queries, mutations, unknown routes, controls, and direct SCADA", () => {
  const cases = [
    classify(livePath, "POST"),
    classify(`${livePath}?extra=1`),
    classify("/api/auth/login?unexpected=1", "POST"),
    classify("/unexpected-write", "POST"),
    classify("/unexpected-read"),
    classify("/"),
    classify("/?extra=1"),
    classify("/?_rsc=expected&extra=1"),
    classify(`${gatePath}?extra=1`),
    classify(`${gatePath}?_rsc=abc123&extra=1`),
    classify("/api/control-authority", "GET"),
    classify("/api/gates/waste-way/command-level", "POST"),
    classify("/api/gates/waste-way/horn", "POST"),
    classify("/api/anything"),
    classify("/api/gates/waste-way/status", "GET", scadaOrigin),
  ];

  for (const result of cases) assert.equal(result.allowed, false);
  assert.equal(cases[0].mutation, true);
  assert.equal(cases[3].mutation, true);
  assert.equal(cases[10].forbiddenPath, true);
  assert.equal(cases[11].forbiddenPath, true);
  assert.equal(cases.at(-1).directScada, true);
});

test("classifies every blocked external request as unallowlisted", () => {
  const result = classify(
    "/api/command",
    "POST",
    "http://external.example.test",
  );

  assert.equal(result.allowed, false);
  assert.equal(result.unallowlisted, true);
});

test("login settles anonymous refresh before submitting real credentials", async () => {
  const events = [];
  let responseCount = 0;
  const page = {
    goto: async (url) => events.push(["goto", url]),
    locator: (selector) => ({
      fill: async (value) => events.push(["fill", selector, value]),
    }),
    waitForResponse: () => {
      responseCount += 1;
      events.push(["wait-response", responseCount]);
      return Promise.resolve({
        status: () => (responseCount === 1 ? 401 : 200),
      });
    },
    getByRole: () => ({
      click: async (options) => events.push(["click", options]),
    }),
  };
  const target = "/read-only/gates/waste-way";

  assert.equal(
    await login(
      page,
      frontendOrigin,
      "operator@example.test",
      "local-test-value",
      target,
    ),
    200,
  );
  assert.deepEqual(events.slice(0, 4), [
    ["wait-response", 1],
    [
      "goto",
      `${frontendOrigin}/login?next=%2Fread-only%2Fgates%2Fwaste-way`,
    ],
    ["fill", "#login-email", "operator@example.test"],
    ["fill", "#login-password", "local-test-value"],
  ]);
  assert.deepEqual(events.at(-2), ["wait-response", 2]);
  assert.deepEqual(events.at(-1), ["click", { noWaitAfter: true }]);
});

test("accepts only hidden coordination files in the evidence root", () => {
  assert.equal(
    validateControlPath(
      "/var/lib/munbon-local-acceptance/evidence/.go-read-ready",
      ".go-read-ready",
    ),
    "/var/lib/munbon-local-acceptance/evidence/.go-read-ready",
  );
  assert.throws(
    () => validateControlPath("/tmp/.go-read-ready", ".go-read-ready"),
    /coordination_path_invalid/,
  );
});
