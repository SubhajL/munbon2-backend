#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");

let checkpoint = "startup";
const EVIDENCE_ROOT = "/var/lib/munbon-local-acceptance/evidence";
const AUTH_REQUESTS = new Map([
  ["/api/auth/login", "POST"],
  ["/api/auth/refresh", "POST"],
  ["/api/auth/logout", "POST"],
]);
const FORBIDDEN_CONTROL_PATH =
  /(?:^|\/)(?:approve|activate|dispatch|authority|control-authority|hold|resume|command|command-level|level|horn)(?:\/|$)/i;

function required(name) {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`missing_${name.toLowerCase()}`);
  return value;
}

function assert(condition, code) {
  if (!condition) throw new Error(code);
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

function hasOnlyRscQuery(parsed) {
  return (
    parsed.searchParams.size === 1 &&
    typeof parsed.searchParams.get("_rsc") === "string" &&
    parsed.searchParams.get("_rsc").length > 0
  );
}

function isAllowedDocumentRequest(parsed, method, allowedDocumentPaths) {
  if (!["GET", "HEAD"].includes(method)) return false;
  if (!allowedDocumentPaths.has(parsed.pathname)) return false;
  if (!parsed.search) return true;
  if (parsed.pathname === "/login") {
    const next = parsed.searchParams.get("next");
    if (
      next === null ||
      next === "/login" ||
      !allowedDocumentPaths.has(next)
    ) {
      return false;
    }
    if (parsed.searchParams.size === 1) return true;
    const rsc = parsed.searchParams.get("_rsc");
    return (
      method === "GET" &&
      parsed.searchParams.size === 2 &&
      rsc !== null &&
      rsc.length > 0
    );
  }
  return hasOnlyRscQuery(parsed);
}

function classifyGateRequest({
  url,
  method,
  frontendOrigin,
  scadaOrigin,
  allowedStatusPaths,
  allowedDocumentPaths,
}) {
  const parsed = new URL(url);
  const normalizedMethod = method.toUpperCase();
  const sameOrigin = parsed.origin === frontendOrigin;
  const directScada = parsed.origin === scadaOrigin;
  const sameOriginApi = sameOrigin && parsed.pathname.startsWith("/api/");
  const allowedAuth =
    sameOriginApi &&
    !parsed.search &&
    AUTH_REQUESTS.get(parsed.pathname) === normalizedMethod;
  const allowedStatus =
    sameOriginApi &&
    !parsed.search &&
    normalizedMethod === "GET" &&
    allowedStatusPaths.has(parsed.pathname);
  const allowedDocument =
    sameOrigin &&
    isAllowedDocumentRequest(parsed, normalizedMethod, allowedDocumentPaths);
  const allowedAsset =
    sameOrigin &&
    ["GET", "HEAD"].includes(normalizedMethod) &&
    !parsed.search &&
    (parsed.pathname.startsWith("/_next/static/") ||
      parsed.pathname === "/favicon.ico");
  const allowedRootRsc =
    sameOrigin &&
    normalizedMethod === "GET" &&
    parsed.pathname === "/" &&
    hasOnlyRscQuery(parsed);
  const allowed =
    sameOrigin &&
    (allowedAuth ||
      allowedStatus ||
      allowedDocument ||
      allowedAsset ||
      allowedRootRsc);
  const unallowlisted = !allowed && !directScada;
  const mutation =
    sameOrigin &&
    !allowedAuth &&
    !["GET", "HEAD", "OPTIONS"].includes(normalizedMethod);
  const forbiddenPath =
    (sameOrigin || directScada) && FORBIDDEN_CONTROL_PATH.test(parsed.pathname);

  return {
    allowed,
    directScada,
    forbiddenPath,
    mutation,
    unallowlisted,
  };
}

async function login(page, baseUrl, email, password, redirectPath) {
  assert(
    /^\/read-only\/gates\/[a-z0-9][a-z0-9-]*$/.test(redirectPath),
    "login_redirect_invalid",
  );
  const bootstrapRefresh = page.waitForResponse(
    (candidate) =>
      candidate.url() === `${baseUrl}/api/auth/refresh` &&
      candidate.request().method() === "POST",
    { timeout: 30000 },
  );
  await page.goto(`${baseUrl}/login?next=${encodeURIComponent(redirectPath)}`, {
    waitUntil: "domcontentloaded",
  });
  assert(
    (await bootstrapRefresh).status() === 401,
    "bootstrap_refresh_not_settled",
  );
  await page.locator("#login-email").fill(email);
  await page.locator("#login-password").fill(password);
  const response = page.waitForResponse(
    (candidate) =>
      candidate.url() === `${baseUrl}/api/auth/login` &&
      candidate.request().method() === "POST",
    { timeout: 30000 },
  );
  await page
    .getByRole("button", { name: "เข้าสู่ระบบ (Sign in)", exact: true })
    .click({ noWaitAfter: true });
  const status = (await response).status();
  assert(status === 200, "login_not_accepted");
  return status;
}

function installRequestBoundary(
  context,
  {
    frontendOrigin,
    scadaOrigin,
    allowedStatusPaths,
    allowedDocumentPaths,
    inventory,
  },
) {
  context.on("request", (request) => {
    const parsed = new URL(request.url());
    const result = classifyGateRequest({
      url: request.url(),
      method: request.method(),
      frontendOrigin,
      scadaOrigin,
      allowedStatusPaths,
      allowedDocumentPaths,
    });
    if (
      inventory.phase === "signed-out" &&
      allowedStatusPaths.has(parsed.pathname)
    ) {
      inventory.signedOutStatusRequests += 1;
    }
    if (result.directScada) {
      inventory.directScadaRequests.push(
        `${request.method()} ${parsed.pathname}`,
      );
    }
    if (result.forbiddenPath) {
      inventory.forbiddenRequests.push(
        `${request.method()} ${parsed.pathname}`,
      );
    }
    if (result.unallowlisted) {
      inventory.unallowlistedRequests.push(
        `${request.method()} ${parsed.pathname}`,
      );
    }
    if (result.mutation) {
      inventory.mutationRequests.push(`${request.method()} ${parsed.pathname}`);
    }
  });
  context.on("response", (response) => {
    const request = response.request();
    const parsed = new URL(response.url());
    if (
      request.method() === "GET" &&
      parsed.pathname === "/api/read-only/gates/waste-way/status" &&
      response.status() === 200
    ) {
      inventory.liveStatusResponses += 1;
    }
  });
  return context.route("**/*", async (route) => {
    const request = route.request();
    const result = classifyGateRequest({
      url: request.url(),
      method: request.method(),
      frontendOrigin,
      scadaOrigin,
      allowedStatusPaths,
      allowedDocumentPaths,
    });
    if (result.allowed) {
      await route.continue();
    } else {
      await route.abort("blockedbyclient");
    }
  });
}

async function responseProof(response) {
  const cacheControl = (await response.headerValue("cache-control")) ?? "";
  return {
    status: response.status(),
    noStore: cacheControl.toLowerCase().includes("no-store"),
  };
}

async function waitForCount(read, minimum, code) {
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    if (read() >= minimum) return;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(code);
}

async function waitForFile(target, code) {
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    if (fs.existsSync(target)) return;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(code);
}

async function main() {
  const { chromium } = require("playwright");
  const baseUrl = required("LOCAL_GATE_WEB_URL");
  const scadaUrl = required("LOCAL_SCADA_URL");
  const email = required("MUNBON_OPERATOR_EMAIL");
  const password = required("MUNBON_OPERATOR_PASSWORD");
  const gateId = required("LOCAL_GATE_ID");
  const readyPath = validateControlPath(
    required("LOCAL_GO_READ_READY_PATH"),
    ".go-read-ready",
  );
  const outageReleasePath = validateControlPath(
    required("LOCAL_GO_READ_OUTAGE_RELEASE_PATH"),
    ".go-read-outage-release",
  );
  const liveScreenshot = validateControlPath(
    required("LOCAL_GO_READ_LIVE_SCREENSHOT"),
    "LOCAL-GO-READ-1-live.png",
  );
  const outageScreenshot = validateControlPath(
    required("LOCAL_GO_READ_OUTAGE_SCREENSHOT"),
    "LOCAL-GO-READ-1-outage.png",
  );
  assert(baseUrl === "http://127.0.0.1:9998", "gate_web_url_invalid");
  assert(scadaUrl === "http://127.0.0.1:3030", "scada_url_invalid");
  assert(gateId === "waste-way", "gate_id_invalid");

  const frontendOrigin = new URL(baseUrl).origin;
  const scadaOrigin = new URL(scadaUrl).origin;
  const livePath = `/api/read-only/gates/${gateId}/status`;
  const unknownPath = "/api/read-only/gates/unknown-gate/status";
  const gatePath = `/read-only/gates/${gateId}`;
  const allowedStatusPaths = new Set([livePath, unknownPath]);
  const allowedDocumentPaths = new Set([
    "/login",
    gatePath,
    "/read-only/gates/unknown-gate",
  ]);
  const inventory = {
    phase: "signed-out",
    signedOutStatusRequests: 0,
    liveStatusResponses: 0,
    directScadaRequests: [],
    forbiddenRequests: [],
    unallowlistedRequests: [],
    mutationRequests: [],
  };

  checkpoint = "browser_launch";
  const browser = await chromium.launch({ headless: true });
  try {
    const signedOutContext = await browser.newContext();
    await installRequestBoundary(signedOutContext, {
      frontendOrigin,
      scadaOrigin,
      allowedStatusPaths,
      allowedDocumentPaths,
      inventory,
    });
    const signedOutPage = await signedOutContext.newPage();
    checkpoint = "signed_out";
    await signedOutPage.goto(`${baseUrl}${gatePath}`, {
      waitUntil: "domcontentloaded",
    });
    await signedOutPage.waitForURL((url) => url.pathname === "/login", {
      timeout: 30000,
    });
    const signedOutRedirect = new URL(signedOutPage.url()).pathname;
    await signedOutPage.waitForTimeout(250);
    await signedOutContext.close();
    assert(
      inventory.signedOutStatusRequests === 0,
      "signed_out_status_request_observed",
    );

    const context = await browser.newContext();
    await installRequestBoundary(context, {
      frontendOrigin,
      scadaOrigin,
      allowedStatusPaths,
      allowedDocumentPaths,
      inventory,
    });
    const page = await context.newPage();
    inventory.phase = "login";
    const initialStatusResponse = page.waitForResponse(
      (candidate) =>
        candidate.url() === `${baseUrl}${livePath}` &&
        candidate.request().method() === "GET" &&
        candidate.status() === 200,
      { timeout: 30000 },
    );
    checkpoint = "login";
    const loginStatus = await login(page, baseUrl, email, password, gatePath);
    await page.waitForURL((url) => url.pathname === gatePath, {
      timeout: 30000,
    });
    const initialResponse = await initialStatusResponse;
    const initialProof = await responseProof(initialResponse);
    const statusBody = await initialResponse.json();
    assert(statusBody.id === gateId, "gate_status_identity_invalid");
    assert(statusBody.name === "Waste Way", "gate_status_name_invalid");
    assert(statusBody.connection === "offline", "gate_status_not_offline");
    assert(initialProof.noStore, "gate_status_cache_control_invalid");
    await page
      .getByRole("heading", { name: "Waste Way", exact: true })
      .waitFor({ state: "visible", timeout: 30000 });
    await page
      .getByText("โหมดดูอย่างเดียว (Read only)", { exact: true })
      .waitFor({ state: "visible", timeout: 30000 });
    await page.getByText(gateId, { exact: true }).waitFor({
      state: "visible",
      timeout: 30000,
    });
    const actionControls = await page
      .locator(
        "main button, main form, main input, main select, main textarea, main [role='button']",
      )
      .count();
    assert(actionControls === 0, "action_controls_visible");
    await page.screenshot({ path: liveScreenshot, fullPage: true });

    checkpoint = "repeated_polling";
    await waitForCount(
      () => inventory.liveStatusResponses,
      3,
      "live_status_response_count_invalid",
    );

    checkpoint = "unknown_gate";
    const unknownResponse = page.waitForResponse(
      (candidate) =>
        candidate.url() === `${baseUrl}${unknownPath}` &&
        candidate.request().method() === "GET",
      { timeout: 30000 },
    );
    await page.goto(`${baseUrl}/read-only/gates/unknown-gate`, {
      waitUntil: "domcontentloaded",
    });
    const unknownProof = await responseProof(await unknownResponse);
    assert(unknownProof.status === 404, "unknown_gate_status_invalid");
    assert(unknownProof.noStore, "unknown_gate_cache_control_invalid");
    await page.locator('main [role="alert"]').waitFor({
      state: "visible",
      timeout: 30000,
    });
    assert(
      (await page.locator("main dl").count()) === 0,
      "unknown_gate_data_visible",
    );

    checkpoint = "restore_live";
    const restoredResponse = page.waitForResponse(
      (candidate) =>
        candidate.url() === `${baseUrl}${livePath}` &&
        candidate.request().method() === "GET" &&
        candidate.status() === 200,
      { timeout: 30000 },
    );
    await page.goto(`${baseUrl}${gatePath}`, { waitUntil: "domcontentloaded" });
    await restoredResponse;
    await page
      .getByRole("heading", { name: "Waste Way", exact: true })
      .waitFor({ state: "visible", timeout: 30000 });

    checkpoint = "outage_coordination";
    const outageResponse = page.waitForResponse(
      (candidate) =>
        candidate.url() === `${baseUrl}${livePath}` &&
        candidate.request().method() === "GET" &&
        candidate.status() === 503,
      { timeout: 30000 },
    );
    fs.writeFileSync(readyPath, "ready\n", { encoding: "utf8", mode: 0o600 });
    await waitForFile(outageReleasePath, "outage_release_missing");
    const outageProof = await responseProof(await outageResponse);
    assert(outageProof.noStore, "outage_cache_control_invalid");
    await page.locator('main [role="alert"]').waitFor({
      state: "visible",
      timeout: 30000,
    });
    const staleStatusHidden = (await page.locator("main dl").count()) === 0;
    assert(staleStatusHidden, "stale_status_visible_after_outage");
    await page.screenshot({ path: outageScreenshot, fullPage: true });

    const forbiddenProductRequests = [
      ...inventory.forbiddenRequests,
      ...inventory.unallowlistedRequests,
    ];
    assert(
      inventory.directScadaRequests.length === 0,
      "direct_scada_browser_request_observed",
    );
    assert(
      forbiddenProductRequests.length === 0,
      "forbidden_product_request_observed",
    );
    assert(
      inventory.mutationRequests.length === 0,
      "product_mutation_request_observed",
    );
    const logout = await context.request.post(`${baseUrl}/api/auth/logout`);
    assert(logout.status() === 200, "logout_not_accepted");
    await context.close();

    process.stdout.write(
      `${JSON.stringify({
        mode: "go-read",
        signed_out_redirect: signedOutRedirect,
        signed_out_status_requests: inventory.signedOutStatusRequests,
        login_status: loginStatus,
        gate_id: statusBody.id,
        gate_name: statusBody.name,
        connection: statusBody.connection,
        read_status: initialProof.status,
        read_no_store: initialProof.noStore,
        live_status_responses: inventory.liveStatusResponses,
        unknown_gate_status: unknownProof.status,
        unknown_gate_no_store: unknownProof.noStore,
        outage_status: outageProof.status,
        outage_no_store: outageProof.noStore,
        outage_alert_visible: true,
        stale_status_hidden: staleStatusHidden,
        action_controls: actionControls,
        same_origin_status_path: livePath,
        direct_scada_browser_requests: inventory.directScadaRequests.length,
        forbidden_product_requests: forbiddenProductRequests,
        product_mutation_requests: inventory.mutationRequests.length,
        request_inventory_scope: "full-signed-out-through-outage",
        screenshots: ["LOCAL-GO-READ-1-live.png", "LOCAL-GO-READ-1-outage.png"],
      })}\n`,
    );
  } finally {
    await browser.close();
  }
}

module.exports = { classifyGateRequest, login, validateControlPath };

if (require.main === module) {
  main().catch((error) => {
    const code =
      error instanceof Error && /^[a-z0-9_]+$/.test(error.message)
        ? error.message
        : `go_read_browser_${checkpoint}_failed`;
    process.stderr.write(`FAIL go_read_browser: ${code}\n`);
    process.exitCode = 1;
  });
}
