"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const { classifyProductRequest } = require("../run-evidence-browser.js");

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
