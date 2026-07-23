#!/usr/bin/env node
"use strict";

const { chromium } = require("playwright");

let checkpoint = "startup";

function required(name) {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`missing_${name.toLowerCase()}`);
  return value;
}

function assert(condition, code) {
  if (!condition) throw new Error(code);
}

async function newLoopbackContext(browser, baseUrl) {
  const context = await browser.newContext();
  const allowedOrigin = new URL(baseUrl).origin;
  const controlPlanMutationRequests = [];
  context.on("request", (request) => {
    const url = new URL(request.url());
    if (
      url.origin === allowedOrigin &&
      url.pathname.startsWith("/api/smart-water-backend/control-plans") &&
      !["GET", "HEAD", "OPTIONS"].includes(request.method())
    ) {
      controlPlanMutationRequests.push(`${request.method()} ${url.pathname}`);
    }
  });
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    const serverProxyAllowed =
      !url.pathname.startsWith("/api/smart-water-backend/") ||
      url.pathname.startsWith("/api/smart-water-backend/control-plans");
    if (url.origin === allowedOrigin && serverProxyAllowed) {
      await route.continue();
    } else {
      await route.abort("blockedbyclient");
    }
  });
  return { context, controlPlanMutationRequests };
}

async function login(page, baseUrl, email, password, navigate = true) {
  if (navigate) {
    await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
  }
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
}

async function runDark(browser, baseUrl, email, password) {
  checkpoint = "dark_login";
  const { context, controlPlanMutationRequests } = await newLoopbackContext(
    browser,
    baseUrl,
  );
  const page = await context.newPage();
  const listPath = "/smart-water/control-plans";
  await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
  await page.evaluate(
    (path) => localStorage.setItem("redirectAfterLogin", path),
    listPath,
  );
  await login(page, baseUrl, email, password, false);
  await page.waitForTimeout(500);
  await page.goto(`${baseUrl}${listPath}`, { waitUntil: "domcontentloaded" });
  checkpoint = "dark_navigation";
  const navigationLinkCount = await page
    .locator('a[href="/smart-water/control-plans"]')
    .count();
  const route = await context.request.get(
    `${baseUrl}/smart-water/control-plans`,
    { maxRedirects: 0 },
  );
  assert(
    controlPlanMutationRequests.length === 0,
    "dark_control_plan_mutation_observed",
  );
  await context.close();
  return {
    mode: "dark",
    signed_in: true,
    navigation_link_count: navigationLinkCount,
    route_status: route.status(),
  };
}

async function countActionControls(context) {
  const actionPattern =
    /approve|activate|dispatch|execute|command|write|authority|อนุมัติ|สั่ง/i;
  let count = 0;
  for (const page of context.pages()) {
    const values = await page
      .locator(
        'a,button,input[type="button"],input[type="submit"],[role="button"],[role="menuitem"],[onclick],[data-action]',
      )
      .evaluateAll((elements) =>
        elements.map((element) =>
          [
            element.textContent,
            element.getAttribute("aria-label"),
            element.getAttribute("title"),
            element.getAttribute("value"),
            element.getAttribute("href"),
            element.getAttribute("data-action"),
          ]
            .filter(Boolean)
            .join(" "),
        ),
      );
    count += values.filter((value) => actionPattern.test(value)).length;
  }
  return count;
}

async function waitForDetail(page, planId) {
  await page.getByRole("heading", { name: planId, exact: true }).waitFor({
    state: "visible",
    timeout: 30000,
  });
  await page.getByText("Plan identity", { exact: true }).waitFor({
    state: "visible",
    timeout: 30000,
  });
}

function projectionPanel(page, title) {
  return page
    .getByRole("heading", { name: title, exact: true })
    .locator(
      'xpath=ancestor::div[contains(concat(" ", normalize-space(@class), " "), " rounded-lg ")][1]',
    );
}

async function runVisible(
  browser,
  baseUrl,
  email,
  password,
  planId,
  planVersion,
) {
  const { context, controlPlanMutationRequests } = await newLoopbackContext(
    browser,
    baseUrl,
  );
  const page = await context.newPage();
  const listPath = "/smart-water/control-plans";
  const detailPath = `${listPath}/${encodeURIComponent(planId)}/versions/${planVersion}`;

  checkpoint = "signed_out_redirect";
  await page.goto(`${baseUrl}${listPath}`, { waitUntil: "domcontentloaded" });
  await page.waitForURL((url) => url.pathname === "/login", {
    timeout: 30000,
  });
  const signedOutRedirect = new URL(page.url()).pathname;

  checkpoint = "visible_login";
  await login(page, baseUrl, email, password, false);
  await page.waitForTimeout(500);
  await page.goto(`${baseUrl}${listPath}`, { waitUntil: "domcontentloaded" });
  checkpoint = "visible_list";
  await page.getByText(planId, { exact: true }).first().waitFor({
    state: "visible",
    timeout: 30000,
  });
  const navigationLinkCount = await page
    .locator('a[href="/smart-water/control-plans"]')
    .count();
  const detailLink = page.locator(`a[href="${detailPath}"]`);
  const listPlanFound = (await detailLink.count()) === 1;
  assert(listPlanFound, "list_plan_missing");
  checkpoint = "visible_detail";
  await detailLink.click();
  await page.waitForURL((url) => url.pathname === detailPath, {
    timeout: 30000,
  });
  await waitForDetail(page, planId);

  checkpoint = "visible_refresh";
  await page.reload({ waitUntil: "domcontentloaded" });
  await waitForDetail(page, planId);
  const refreshPreservedDetail = new URL(page.url()).pathname === detailPath;

  checkpoint = "visible_deep_link";
  const deepLinkPage = await context.newPage();
  await deepLinkPage.goto(`${baseUrl}${detailPath}`, {
    waitUntil: "domcontentloaded",
  });
  await waitForDetail(deepLinkPage, planId);
  const deepLinkLoaded = new URL(deepLinkPage.url()).pathname === detailPath;

  checkpoint = "visible_missing_plan";
  const missingPage = await context.newPage();
  const missingPath = `${listPath}/00000000-0000-0000-0000-000000000000/versions/1`;
  await missingPage.goto(`${baseUrl}${missingPath}`, {
    waitUntil: "domcontentloaded",
  });
  let missingPlanAlerts = 0;
  for (const title of [
    "Plan detail",
    "Prediction coverage",
    "Predicted ledger",
    "Lifecycle history",
  ]) {
    const alerts = projectionPanel(missingPage, title).locator(
      '[role="alert"]',
    );
    await alerts.first().waitFor({ state: "visible", timeout: 30000 });
    missingPlanAlerts += await alerts.count();
  }

  checkpoint = "visible_panel_failure";
  const failurePage = await context.newPage();
  const ledgerPath = `/api/smart-water-backend/control-plans/${planId}/versions/${planVersion}/ledger`;
  await failurePage.route(`**${ledgerPath}`, async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        success: false,
        error: "Injected local ledger outage",
      }),
      headers: { "Cache-Control": "no-store" },
    });
  });
  await failurePage.goto(`${baseUrl}${detailPath}`, {
    waitUntil: "domcontentloaded",
  });
  await waitForDetail(failurePage, planId);
  await failurePage.locator('[role="alert"]').first().waitFor({
    state: "visible",
    timeout: 30000,
  });
  await failurePage
    .getByText("predicted · not observed", { exact: true })
    .first()
    .waitFor({ state: "visible", timeout: 30000 });
  await failurePage.getByText("Plan identity", { exact: true }).waitFor({
    state: "visible",
    timeout: 30000,
  });
  await failurePage.getByText(/Current: .*No machine authority/).waitFor({
    state: "visible",
    timeout: 30000,
  });
  const ledgerAlerts = await projectionPanel(failurePage, "Predicted ledger")
    .locator('[role="alert"]')
    .count();
  let otherPanelAlerts = 0;
  for (const title of [
    "Plan detail",
    "Prediction coverage",
    "Lifecycle history",
  ]) {
    otherPanelAlerts += await projectionPanel(failurePage, title)
      .locator('[role="alert"]')
      .count();
  }
  assert(
    ledgerAlerts === 1,
    `panel_failure_ledger_alert_count_${ledgerAlerts}`,
  );
  assert(
    otherPanelAlerts === 0,
    `panel_failure_other_alert_count_${otherPanelAlerts}`,
  );
  const actionControls = await countActionControls(context);
  const unexpectedControlPlanMutations = controlPlanMutationRequests.length;
  assert(actionControls === 0, `action_controls_found_${actionControls}`);
  assert(
    unexpectedControlPlanMutations === 0,
    `control_plan_mutations_observed_${unexpectedControlPlanMutations}`,
  );
  const mutationRoutePaths = [
    "/api/smart-water-backend/control-plans",
    `/api/smart-water-backend/control-plans/${planId}/versions/${planVersion}/approve`,
    `/api/smart-water-backend/control-plans/${planId}/versions/${planVersion}/activate`,
    `/api/smart-water-backend/control-plans/${planId}/versions/${planVersion}/dispatch`,
    `/api/smart-water-backend/control-plans/${planId}/versions/${planVersion}/authority`,
  ];
  const mutationRouteStatuses = [];
  for (const path of mutationRoutePaths) {
    const response = await context.request.fetch(`${baseUrl}${path}`, {
      method: "POST",
      data: {},
      maxRedirects: 0,
    });
    mutationRouteStatuses.push(response.status());
  }
  assert(
    mutationRouteStatuses.every((status) => status === 404 || status === 405),
    `mutation_route_exposed_${mutationRouteStatuses.join("_")}`,
  );

  await context.close();
  return {
    mode: "visible",
    signed_out_redirect: signedOutRedirect,
    navigation_link_count: navigationLinkCount,
    list_plan_found: listPlanFound,
    detail_plan_id: planId,
    detail_plan_version: planVersion,
    refresh_preserved_detail: refreshPreservedDetail,
    deep_link_loaded: deepLinkLoaded,
    missing_plan_alerts: missingPlanAlerts,
    independent_panel_failure: "ledger-only",
    action_controls: actionControls,
    unexpected_control_plan_mutations: unexpectedControlPlanMutations,
    mutation_route_denial_count: mutationRouteStatuses.length,
  };
}

async function main() {
  const mode = required("LOCAL_READ_MODE");
  assert(mode === "dark" || mode === "visible", "mode_invalid");
  const baseUrl = required("LOCAL_FRONTEND_URL");
  const email = required("MUNBON_OPERATOR_EMAIL");
  const password = required("MUNBON_OPERATOR_PASSWORD");
  const planId = required("LOCAL_PLAN_ID");
  const planVersion = Number(required("LOCAL_PLAN_VERSION"));
  assert(
    Number.isInteger(planVersion) && planVersion > 0,
    "plan_version_invalid",
  );

  checkpoint = "browser_launch";
  const browser = await chromium.launch({ headless: true });
  try {
    const result =
      mode === "dark"
        ? await runDark(browser, baseUrl, email, password)
        : await runVisible(
            browser,
            baseUrl,
            email,
            password,
            planId,
            planVersion,
          );
    process.stdout.write(`${JSON.stringify(result)}\n`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  const code =
    error instanceof Error && /^[a-z0-9_]+$/.test(error.message)
      ? error.message
      : `browser_${checkpoint}_failed`;
  process.stderr.write(`FAIL read_browser: ${code}\n`);
  process.exitCode = 1;
});
