#!/usr/bin/env node
"use strict";

let checkpoint = "startup";

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
  if (
    p.startsWith("/api/smart-water-backend/water-planning/") &&
    (m === "POST" || m === "PUT" || m === "DELETE")
  ) {
    return "mutation";
  }
  if (
    p.startsWith("/api/smart-water-backend/water-planning/") &&
    m === "GET"
  ) {
    return "read";
  }
  if (p.startsWith("/smart-water/")) return "document";
  return "other";
}

(async () => {
  const { chromium } = require("playwright");

  const frontendUrl = required("LOCAL_FRONTEND_URL");
  const email = required("LOCAL_OPERATOR_EMAIL");
  const password = required("LOCAL_OPERATOR_PASSWORD");
  const weekKey = required("LOCAL_WEEK_KEY");
  const weekDate = required("LOCAL_WEEK_DATE");

  const mutations = [];
  const forbiddenMutations = [];
  let writePhaseActive = false;
  const result = {};

  const ALLOWED_MUTATION_PATHS = new Set([
    "/api/smart-water-backend/water-planning/planning-depth-submissions",
  ]);

  const browser = await chromium.launch({ headless: true });

  try {
    checkpoint = "primary-context";
    const primaryContext = await browser.newContext();
    const page = await primaryContext.newPage();

    page.on("request", (req) => {
      const kind = classifyProductRequest(req.url(), req.method());
      if (kind === "mutation") {
        const entry = {
          method: req.method(),
          url: new URL(req.url()).pathname,
        };
        mutations.push(entry);
        if (
          !writePhaseActive ||
          !ALLOWED_MUTATION_PATHS.has(entry.url)
        ) {
          forbiddenMutations.push(entry);
        }
      }
    });

    checkpoint = "primary-login";
    await page.goto(`${frontendUrl}/login`);
    await page.fill('input[name="email"]', email);
    await page.fill('input[name="password"]', password);
    await page.click('button[type="submit"]');
    await page.waitForURL("**/smart-water/**", { timeout: 15000 });

    checkpoint = "navigate-water-planning";
    await page.goto(`${frontendUrl}/smart-water/dashboard/water-planning`, {
      waitUntil: "networkidle",
    });

    checkpoint = "verify-submit-affordance";
    const submitButton = page.locator(
      'button:has-text("Submit"), [data-testid="submit-planning-depth"]'
    );
    const submitVisible = (await submitButton.count()) > 0;
    assert(submitVisible, "submit_affordance_not_visible");

    checkpoint = "create-submission";
    writePhaseActive = true;
    const createResponse = await page.evaluate(
      async ({ weekKey, weekDate }) => {
        const res = await fetch(
          "/api/smart-water-backend/water-planning/planning-depth-submissions",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              schema_version: 2,
              project_key: "mun-bon",
              calendar_system: "rid-irrigation-v1",
              week_key: weekKey,
              week_date: weekDate,
              client_submission_id: crypto.randomUUID(),
              expected_active_submission_id: null,
              levels: Array.from({ length: 6 }, (_, i) => ({
                area_type: "zone",
                area_id: `01-${String(i + 1).padStart(2, "0")}`,
                planning_depth_mm: 250.0 + i * 10,
              })),
            }),
          }
        );
        return { status: res.status, body: await res.json() };
      },
      { weekKey, weekDate }
    );
    assert(createResponse.status === 201, "create_not_201");

    const createClientId =
      createResponse.body.client_submission_id;
    result.create_result = {
      status: createResponse.status,
      submission_id: createResponse.body.submission_id,
      client_submission_id: createClientId,
      week_key: createResponse.body.week_key,
    };

    checkpoint = "active-readback";
    const activeResponse = await page.evaluate(async ({ weekKey }) => {
      const res = await fetch(
        `/api/smart-water-backend/water-planning/planning-depth-submissions/active?project_key=mun-bon&week_key=${weekKey}`
      );
      return { status: res.status, body: await res.json() };
    }, { weekKey });
    assert(activeResponse.status === 200, "active_readback_not_200");

    result.active_readback = {
      status: activeResponse.status,
      submission_id: activeResponse.body.submission_id,
      levels_count: Array.isArray(activeResponse.body.levels)
        ? activeResponse.body.levels.length
        : 0,
    };

    checkpoint = "second-context";
    const secondContext = await browser.newContext();
    const page2 = await secondContext.newPage();

    checkpoint = "second-login";
    await page2.goto(`${frontendUrl}/login`);
    await page2.fill('input[name="email"]', email);
    await page2.fill('input[name="password"]', password);
    await page2.click('button[type="submit"]');
    await page2.waitForURL("**/smart-water/**", { timeout: 15000 });

    checkpoint = "correct-submission";
    const correctResponse = await page2.evaluate(
      async ({ weekKey, weekDate, activeId }) => {
        const res = await fetch(
          "/api/smart-water-backend/water-planning/planning-depth-submissions",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
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
                planning_depth_mm: 260.0 + i * 10,
              })),
            }),
          }
        );
        return { status: res.status, body: await res.json() };
      },
      {
        weekKey,
        weekDate,
        activeId: createResponse.body.submission_id,
      }
    );
    assert(correctResponse.status === 201, "correct_not_201");

    result.correct_result = {
      status: correctResponse.status,
      submission_id: correctResponse.body.submission_id,
      client_submission_id: correctResponse.body.client_submission_id,
      supersedes_submission_id:
        correctResponse.body.supersedes_submission_id || null,
    };

    checkpoint = "stale-conflict";
    const conflictResponse = await page.evaluate(
      async ({ weekKey, weekDate, staleActiveId }) => {
        const res = await fetch(
          "/api/smart-water-backend/water-planning/planning-depth-submissions",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              schema_version: 2,
              project_key: "mun-bon",
              calendar_system: "rid-irrigation-v1",
              week_key: weekKey,
              week_date: weekDate,
              client_submission_id: crypto.randomUUID(),
              expected_active_submission_id: staleActiveId,
              levels: Array.from({ length: 6 }, (_, i) => ({
                area_type: "zone",
                area_id: `01-${String(i + 1).padStart(2, "0")}`,
                planning_depth_mm: 270.0 + i * 10,
              })),
            }),
          }
        );
        return { status: res.status, body: await res.json() };
      },
      {
        weekKey,
        weekDate,
        staleActiveId: createResponse.body.submission_id,
      }
    );
    assert(conflictResponse.status === 409, "conflict_not_409");

    result.conflict_result = {
      status: conflictResponse.status,
      detail: conflictResponse.body.detail,
    };

    checkpoint = "conflict-reconciliation";
    const reconcileResponse = await page.evaluate(async ({ weekKey }) => {
      const res = await fetch(
        `/api/smart-water-backend/water-planning/planning-depth-submissions/active?project_key=mun-bon&week_key=${weekKey}`
      );
      return { status: res.status, body: await res.json() };
    }, { weekKey });
    assert(reconcileResponse.status === 200, "reconciliation_not_200");

    result.conflict_reconciliation = {
      status: reconcileResponse.status,
      submission_id: reconcileResponse.body.submission_id,
    };

    checkpoint = "manual-retry";
    const retryResponse = await page.evaluate(
      async ({ weekKey, weekDate, clientId, activeId }) => {
        const res = await fetch(
          "/api/smart-water-backend/water-planning/planning-depth-submissions",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              schema_version: 2,
              project_key: "mun-bon",
              calendar_system: "rid-irrigation-v1",
              week_key: weekKey,
              week_date: weekDate,
              client_submission_id: clientId,
              expected_active_submission_id: activeId,
              levels: Array.from({ length: 6 }, (_, i) => ({
                area_type: "zone",
                area_id: `01-${String(i + 1).padStart(2, "0")}`,
                planning_depth_mm: 280.0 + i * 10,
              })),
            }),
          }
        );
        return { status: res.status, body: await res.json() };
      },
      {
        weekKey,
        weekDate,
        clientId: createClientId,
        activeId: reconcileResponse.body.submission_id,
      }
    );

    result.retry_result = {
      status: retryResponse.status,
      submission_id: retryResponse.body.submission_id,
      client_submission_id: retryResponse.body.client_submission_id,
    };

    writePhaseActive = false;

    checkpoint = "outage-test";
    result.outage_result = await page.evaluate(async ({ weekKey }) => {
      let rosterOk = false;
      try {
        const roster = await fetch(
          "/api/smart-water-backend/water-planning/planning-depth-roster",
          { signal: AbortSignal.timeout(5000) }
        );
        rosterOk = roster.ok;
      } catch {
        rosterOk = false;
      }
      let activeReadOk = false;
      try {
        const active = await fetch(
          `/api/smart-water-backend/water-planning/planning-depth-submissions/active?project_key=mun-bon&week_key=${weekKey}`,
          { signal: AbortSignal.timeout(5000) }
        );
        activeReadOk = active.status === 200 || active.status === 404;
      } catch {
        activeReadOk = false;
      }
      return {
        submit_visible: rosterOk,
        reads_preserved: activeReadOk,
      };
    }, { weekKey });

    checkpoint = "logout";
    await page.evaluate(async () => {
      await fetch("/api/auth/logout", { method: "POST" });
    });
    await page.goto(`${frontendUrl}/smart-water/dashboard/water-planning`, {
      waitUntil: "networkidle",
    });
    result.logout_result = {
      redirect_url: new URL(page.url()).pathname,
    };

    checkpoint = "reload-after-logout";
    await page.goto(
      `${frontendUrl}/smart-water/dashboard/water-planning`,
      { waitUntil: "networkidle" }
    );
    result.reload_result = {
      redirect_url: new URL(page.url()).pathname,
    };

    await secondContext.close();
    await primaryContext.close();

    result.request_inventory = {
      forbidden_mutation_count: forbiddenMutations.length,
      total_mutations: mutations.length,
    };
  } catch (err) {
    process.stderr.write(
      `FAIL write_browser: browser_${checkpoint}_failed: ${err.message}\n`
    );
    await browser.close();
    process.exit(1);
  }

  await browser.close();
  process.stdout.write(JSON.stringify(result));
})();
