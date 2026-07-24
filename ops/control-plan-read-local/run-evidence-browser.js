#!/usr/bin/env node
"use strict";

let checkpoint = "startup";
const FORBIDDEN_CONTROL_PATH =
  /(?:^|\/)(?:approve|activate|dispatch|authority|control-authority|hold|resume|command|command-level|level|horn)(?:\/|$)/i;
const AUTH_REQUESTS = new Map([
  ["/api/auth/login", "POST"],
  ["/api/auth/refresh", "POST"],
  ["/api/auth/logout", "POST"],
]);

function required(name) {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`missing_${name.toLowerCase()}`);
  return value;
}

function assert(condition, code) {
  if (!condition) throw new Error(code);
}

function classifyProductRequest({
  url,
  method,
  frontendOrigin,
  gateOrigin,
  allowedReadPaths,
}) {
  const parsed = new URL(url);
  const normalizedMethod = method.toUpperCase();
  const sameOrigin = parsed.origin === frontendOrigin;
  const gateOperation = parsed.origin === gateOrigin;
  const sameOriginApi = sameOrigin && parsed.pathname.startsWith("/api/");
  const allowedAuth =
    sameOriginApi &&
    AUTH_REQUESTS.get(parsed.pathname) === normalizedMethod;
  const allowedRead =
    sameOriginApi &&
    normalizedMethod === "GET" &&
    allowedReadPaths.has(parsed.pathname);
  const unexpectedApi = sameOriginApi && !allowedAuth && !allowedRead;
  const mutation =
    sameOriginApi &&
    !allowedAuth &&
    !["GET", "HEAD", "OPTIONS"].includes(normalizedMethod);
  const forbiddenPath =
    (sameOriginApi || gateOperation) &&
    FORBIDDEN_CONTROL_PATH.test(parsed.pathname);

  return {
    allowed: sameOrigin && (!sameOriginApi || allowedAuth || allowedRead),
    forbiddenPath,
    gateOperation,
    mutation,
    unexpectedApi,
  };
}

async function login(page, baseUrl, email, password, redirectPath) {
  assert(
    /^\/smart-water\/control-plans\/[0-9a-f-]+\/versions\/[1-9][0-9]*$/.test(
      redirectPath,
    ),
    "login_redirect_invalid",
  );
  await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
  await page.evaluate(
    (path) => localStorage.setItem("redirectAfterLogin", path),
    redirectPath,
  );
  await page.locator("#email").fill(email);
  await page.locator("#password").fill(password);
  const response = page.waitForResponse(
    (candidate) =>
      candidate.url() === `${baseUrl}/api/auth/login` &&
      candidate.request().method() === "POST",
    { timeout: 30000 },
  );
  await page.getByRole("button", { name: "เข้าสู่ระบบ", exact: true }).click();
  assert((await response).status() === 200, "login_not_accepted");
  await page.waitForTimeout(500);
}

function evidencePanel(page, title) {
  return page.getByRole("region", { name: title, exact: true });
}

async function waitForProjectionProofs(proofs, expectedCount) {
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    if (proofs.size === expectedCount) return;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("projection_response_inventory_incomplete");
}

async function main() {
  const { chromium } = require("playwright");
  const baseUrl = required("LOCAL_FRONTEND_URL");
  const gateBaseUrl = required("LOCAL_GATE_OPERATIONS_URL");
  const email = required("MUNBON_OPERATOR_EMAIL");
  const password = required("MUNBON_OPERATOR_PASSWORD");
  const planId = required("LOCAL_PLAN_ID");
  const planVersion = Number(required("LOCAL_PLAN_VERSION"));
  const gateId = required("LOCAL_GATE_ID");
  assert(
    Number.isInteger(planVersion) && planVersion > 0,
    "plan_version_invalid",
  );
  assert(gateId === "waste-way", "gate_id_invalid");

  const frontendOrigin = new URL(baseUrl).origin;
  const gateOrigin = new URL(gateBaseUrl).origin;
  const detailPath =
    `/smart-water/control-plans/${encodeURIComponent(planId)}` +
    `/versions/${planVersion}`;
  const projectionNames = [
    "execution-state",
    "intent-timeline",
    "readback-observations",
  ];
  const projectionPath = (name, identity = planId, version = planVersion) =>
    `/api/smart-water-backend/control-plans/${encodeURIComponent(identity)}` +
    `/versions/${version}/${name}`;
  const expectedProjectionPaths = projectionNames.map((name) =>
    projectionPath(name),
  );
  const allowedReadPaths = new Set();
  for (const [identity, version] of [
    [planId, planVersion],
    ["00000000-0000-0000-0000-000000000000", 1],
  ]) {
    const identityRoot =
      `/api/smart-water-backend/control-plans/${encodeURIComponent(identity)}` +
      `/versions/${version}`;
    for (const suffix of [
      "",
      "/prediction-coverage",
      "/ledger",
      "/lifecycle-history",
      "/intent-timeline",
      "/readback-observations",
      "/execution-state",
    ]) {
      allowedReadPaths.add(`${identityRoot}${suffix}`);
    }
  }

  checkpoint = "browser_launch";
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const projectionProofs = new Map();
  const forbiddenProductRequests = [];
  const productMutationRequests = [];
  const gateOperationsRequests = [];

  context.on("request", (request) => {
    const url = new URL(request.url());
    const method = request.method();
    const inventory = classifyProductRequest({
      url: request.url(),
      method,
      frontendOrigin,
      gateOrigin,
      allowedReadPaths,
    });
    if (inventory.gateOperation) {
      gateOperationsRequests.push(`${method} ${url.pathname}`);
    }
    if (inventory.mutation) {
      productMutationRequests.push(`${method} ${url.pathname}`);
    }
    if (inventory.forbiddenPath || inventory.unexpectedApi) {
      forbiddenProductRequests.push(`${method} ${url.pathname}`);
    }
  });
  context.on("response", async (response) => {
    const request = response.request();
    const path = new URL(response.url()).pathname;
    const index = expectedProjectionPaths.indexOf(path);
    if (
      index === -1 ||
      request.method() !== "GET" ||
      projectionProofs.has(projectionNames[index])
    ) {
      return;
    }
    const cacheControl = (await response.headerValue("cache-control")) ?? "";
    projectionProofs.set(projectionNames[index], {
      status: response.status(),
      noStore: cacheControl.toLowerCase().includes("no-store"),
    });
  });
  await context.route("**/*", async (route) => {
    const request = route.request();
    const inventory = classifyProductRequest({
      url: request.url(),
      method: request.method(),
      frontendOrigin,
      gateOrigin,
      allowedReadPaths,
    });
    if (inventory.allowed) {
      await route.continue();
    } else {
      await route.abort("blockedbyclient");
    }
  });

  try {
    const page = await context.newPage();
    checkpoint = "login";
    await login(page, baseUrl, email, password, detailPath);

    checkpoint = "present_held";
    await page.goto(`${baseUrl}${detailPath}`, {
      waitUntil: "domcontentloaded",
    });
    await page
      .getByRole("heading", { name: "Machine execution evidence", exact: true })
      .waitFor({ state: "visible", timeout: 30000 });
    for (const title of [
      "Intent timeline",
      "Readback observations",
      "Execution state",
    ]) {
      await evidencePanel(page, title).waitFor({
        state: "visible",
        timeout: 30000,
      });
    }
    await page
      .getByText("Currently held", { exact: true })
      .waitFor({ state: "visible", timeout: 30000 });
    await page
      .getByText("No command intents are recorded.", { exact: true })
      .waitFor({ state: "visible", timeout: 30000 });
    await page
      .getByText("Empty intent history does not claim execution.", {
        exact: true,
      })
      .waitFor({ state: "visible", timeout: 30000 });
    const gateLinkLocator = page.getByRole("link", {
      name: `Open read-only Gate Operations for ${gateId}`,
      exact: true,
    });
    await gateLinkLocator.waitFor({ state: "visible", timeout: 30000 });
    const gateLink = await gateLinkLocator.getAttribute("href");
    const expectedGateLink = `${gateBaseUrl}/${encodeURIComponent(gateId)}`;
    assert(gateLink === expectedGateLink, "gate_link_not_exact");
    await waitForProjectionProofs(projectionProofs, projectionNames.length);
    const projectionStatuses = Object.fromEntries(
      projectionNames.map((name) => [name, projectionProofs.get(name).status]),
    );
    const projectionNoStoreCount = projectionNames.filter(
      (name) => projectionProofs.get(name).noStore,
    ).length;
    assert(
      Object.values(projectionStatuses).every((status) => status === 200),
      "projection_status_not_accepted",
    );
    assert(
      projectionNoStoreCount === projectionNames.length,
      "projection_cache_control_not_accepted",
    );
    const evidencePanelCount = await page
      .locator('section[role="region"]')
      .count();
    assert(evidencePanelCount === 3, "evidence_panel_count_invalid");

    checkpoint = "absent";
    const missingPage = await context.newPage();
    const missingId = "00000000-0000-0000-0000-000000000000";
    await missingPage.goto(
      `${baseUrl}/smart-water/control-plans/${missingId}/versions/1`,
      { waitUntil: "domcontentloaded" },
    );
    let absentProjectionAlerts = 0;
    for (const title of [
      "Intent timeline",
      "Readback observations",
      "Execution state",
    ]) {
      const alert = evidencePanel(missingPage, title).getByRole("alert");
      await alert.waitFor({ state: "visible", timeout: 30000 });
      absentProjectionAlerts += await alert.count();
    }
    assert(absentProjectionAlerts === 3, "absent_projection_alerts_invalid");

    checkpoint = "unavailable";
    const unavailablePage = await context.newPage();
    const unavailablePath = projectionPath("readback-observations");
    await unavailablePage.route(`**${unavailablePath}`, async (route) => {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          success: false,
          error: "Injected local evidence outage",
        }),
        headers: { "Cache-Control": "no-store" },
      });
    });
    await unavailablePage.goto(`${baseUrl}${detailPath}`, {
      waitUntil: "domcontentloaded",
    });
    await evidencePanel(unavailablePage, "Readback observations")
      .getByRole("alert")
      .waitFor({ state: "visible", timeout: 30000 });
    await unavailablePage
      .getByText("Currently held", { exact: true })
      .waitFor({ state: "visible", timeout: 30000 });

    checkpoint = "malformed";
    const malformedPage = await context.newPage();
    const malformedPath = projectionPath("intent-timeline");
    await malformedPage.route(`**${malformedPath}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ unexpected: true }),
        headers: { "Cache-Control": "no-store" },
      });
    });
    await malformedPage.goto(`${baseUrl}${detailPath}`, {
      waitUntil: "domcontentloaded",
    });
    await evidencePanel(malformedPage, "Intent timeline")
      .getByRole("alert")
      .waitFor({ state: "visible", timeout: 30000 });
    await malformedPage
      .getByText("Currently held", { exact: true })
      .waitFor({ state: "visible", timeout: 30000 });

    assert(
      gateOperationsRequests.length === 0,
      "gate_operations_navigation_observed",
    );
    assert(
      forbiddenProductRequests.length === 0,
      "forbidden_product_request_observed",
    );
    assert(
      productMutationRequests.length === 0,
      "product_mutation_request_observed",
    );

    process.stdout.write(
      `${JSON.stringify({
        mode: "evidence-visible",
        projection_statuses: projectionStatuses,
        projection_no_store_count: projectionNoStoreCount,
        evidence_panel_count: evidencePanelCount,
        absent_projection_alerts: absentProjectionAlerts,
        unavailable_projection: "readback-observations",
        malformed_projection: "intent-timeline",
        intent_timeline_state: "empty-not-execution",
        held_state: true,
        gate_link: gateLink,
        gate_operations_navigation_requests: gateOperationsRequests.length,
        evidence_request_paths: expectedProjectionPaths,
        forbidden_product_requests: forbiddenProductRequests,
        product_mutation_requests: productMutationRequests.length,
      })}\n`,
    );
  } finally {
    await context.close();
    await browser.close();
  }
}

module.exports = { classifyProductRequest, login };

if (require.main === module) {
  main().catch((error) => {
    const code =
      error instanceof Error && /^[a-z0-9_]+$/.test(error.message)
        ? error.message
        : `evidence_browser_${checkpoint}_failed`;
    process.stderr.write(`FAIL evidence_browser: ${code}\n`);
    process.exitCode = 1;
  });
}
