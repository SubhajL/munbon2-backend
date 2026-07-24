"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const {
  classifyProductRequest,
  login,
} = require("../run-evidence-browser.js");

const frontendOrigin = "http://127.0.0.1:9999";
const gateOrigin = "http://127.0.0.1:9998";
const allowedPath =
  "/api/smart-water-backend/control-plans/plan-id/versions/3/execution-state";
const allowedReadPaths = new Set([allowedPath]);

function classify(path, method = "GET", origin = frontendOrigin) {
  return classifyProductRequest({
    url: `${origin}${path}`,
    method,
    frontendOrigin,
    gateOrigin,
    allowedReadPaths,
  });
}

test("allows only exact auth posts and allowlisted projection reads", () => {
  assert.equal(classify("/api/auth/login", "POST").allowed, true);
  assert.equal(classify("/api/auth/refresh", "POST").allowed, true);
  assert.equal(classify(allowedPath).allowed, true);
  assert.equal(classify(allowedPath).unexpectedApi, false);
});

test("rejects authority, gate command, mutation, and unknown API requests", () => {
  const cases = [
    classify("/api/control-authority", "POST"),
    classify("/api/gates/waste-way/command-level", "POST"),
    classify(allowedPath, "POST"),
    classify("/api/anything"),
  ];

  for (const result of cases) {
    assert.equal(result.allowed, false);
    assert.equal(result.unexpectedApi, true);
  }
  assert.equal(cases[0].mutation, true);
  assert.equal(cases[1].forbiddenPath, true);
  assert.equal(cases[2].mutation, true);
});

test("scopes login to plan detail before submitting credentials", async () => {
  const events = [];
  let responseCount = 0;
  const page = {
    goto: async (url) => events.push(["goto", url]),
    evaluate: async (_callback, path) => events.push(["redirect", path]),
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
  const detailPath =
    "/smart-water/control-plans/00000000-0000-0000-0000-000000000000/versions/3";

  await login(
    page,
    frontendOrigin,
    "operator@example.test",
    "local-test-value",
    detailPath,
  );

  assert.deepEqual(events.slice(0, 5), [
    ["wait-response", 1],
    ["goto", `${frontendOrigin}/login`],
    ["redirect", detailPath],
    ["fill", "#email", "operator@example.test"],
    ["fill", "#password", "local-test-value"],
  ]);
  assert.deepEqual(events.at(-2), ["wait-response", 2]);
  assert.deepEqual(events.at(-1), ["click", { noWaitAfter: true }]);
  await assert.rejects(
    login(
      page,
      frontendOrigin,
      "operator@example.test",
      "local-test-value",
      "/smart-water/dashboard",
    ),
    /login_redirect_invalid/,
  );
});
