/**
 * F-08 boot smoke test: the service previously crashed on startup because
 * `src/index.js` did `require('./jobs/job-scheduler')` and the module did not exist
 * (MODULE_NOT_FOUND). These tests assert the module resolves and exposes the exact
 * interface `index.js` uses: `JobScheduler.getInstance()` -> `{ start, stop }`.
 */
const { JobScheduler } = require("./job-scheduler");

describe("JobScheduler (F-08 boot smoke test)", () => {
  test("module resolves and exports the JobScheduler class", () => {
    expect(typeof JobScheduler).toBe("function");
  });

  test("getInstance() returns a singleton exposing async start/stop", () => {
    const a = JobScheduler.getInstance();
    const b = JobScheduler.getInstance();
    expect(a).toBe(b);
    expect(typeof a.start).toBe("function");
    expect(typeof a.stop).toBe("function");
  });

  test("the require target from index.js no longer throws", () => {
    expect(() => require("./job-scheduler")).not.toThrow();
  });
});
