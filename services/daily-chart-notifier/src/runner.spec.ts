import { describe, expect, test, vi, beforeEach } from "vitest";
import { runDailyJob } from "./runner";
import type { Config } from "./types";

vi.mock("./screenshot", () => ({
  captureScreenshots: vi
    .fn()
    .mockResolvedValue(["/tmp/screenshot-0.png", "/tmp/screenshot-1.png"]),
}));

vi.mock("./log-fetcher", () => ({
  fetchPm2Logs: vi.fn().mockResolvedValue("Log line 1\nLog line 2\n"),
}));

vi.mock("./email", () => ({
  sendEmail: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("./utils/temp", () => ({
  createTempWorkspace: vi.fn().mockReturnValue({
    dir: "/tmp/test-workspace",
    screenshotDir: "/tmp/test-workspace/screenshots",
    cleanup: vi.fn(),
  }),
}));

const mockConfig: Config = {
  smtp: {
    host: "smtp.gmail.com",
    port: 587,
    user: "sender@example.com",
    pass: "app-password",
    from: "Munbon Daily Report <sender@example.com>",
  },
  email: { to: "recipient@example.com" },
  ssh: {
    host: "192.168.1.1",
    port: 22,
    user: "ubuntu",
    keyPath: "/path/to/key.pem",
  },
  dashboards: {
    moistureUrl: "http://localhost:8080/moisture.html",
    waterLevelUrl: "http://localhost:8080/water.html",
  },
  pm2LogPath: "~/.pm2/logs/app-out.log",
  timezone: "Asia/Bangkok",
};

describe("runDailyJob", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("captures screenshots from configured dashboard URLs", async () => {
    const { captureScreenshots } = await import("./screenshot");

    await runDailyJob(mockConfig);

    expect(captureScreenshots).toHaveBeenCalledWith(
      [mockConfig.dashboards.moistureUrl, mockConfig.dashboards.waterLevelUrl],
      expect.any(String),
    );
  });

  test("fetches PM2 logs from EC2", async () => {
    const { fetchPm2Logs } = await import("./log-fetcher");

    await runDailyJob(mockConfig);

    expect(fetchPm2Logs).toHaveBeenCalledWith(mockConfig);
  });

  test("sends email with screenshots and logs", async () => {
    const { sendEmail } = await import("./email");

    await runDailyJob(mockConfig);

    expect(sendEmail).toHaveBeenCalledWith(
      mockConfig,
      expect.arrayContaining([
        expect.objectContaining({ filename: "moisture-dashboard.png" }),
        expect.objectContaining({ filename: "water-level-dashboard.png" }),
        expect.objectContaining({ filename: "pm2-logs.txt" }),
      ]),
    );
  });

  test("cleans up temp files on success", async () => {
    const { createTempWorkspace } = await import("./utils/temp");
    const mockCleanup = vi.fn();
    (createTempWorkspace as any).mockReturnValue({
      dir: "/tmp/test-workspace",
      screenshotDir: "/tmp/test-workspace/screenshots",
      cleanup: mockCleanup,
    });

    await runDailyJob(mockConfig);

    expect(mockCleanup).toHaveBeenCalled();
  });

  test("cleans up temp files even on screenshot error", async () => {
    const { captureScreenshots } = await import("./screenshot");
    const { createTempWorkspace } = await import("./utils/temp");
    const mockCleanup = vi.fn();
    (createTempWorkspace as any).mockReturnValue({
      dir: "/tmp/test-workspace",
      screenshotDir: "/tmp/test-workspace/screenshots",
      cleanup: mockCleanup,
    });
    (captureScreenshots as any).mockRejectedValueOnce(
      new Error("Browser error"),
    );

    const result = await runDailyJob(mockConfig);

    expect(mockCleanup).toHaveBeenCalled();
    expect(result.success).toBe(false);
    expect(result.error).toContain("Browser error");
  });

  test("cleans up temp files even on email error", async () => {
    const { sendEmail } = await import("./email");
    const { createTempWorkspace } = await import("./utils/temp");
    const mockCleanup = vi.fn();
    (createTempWorkspace as any).mockReturnValue({
      dir: "/tmp/test-workspace",
      screenshotDir: "/tmp/test-workspace/screenshots",
      cleanup: mockCleanup,
    });
    (sendEmail as any).mockRejectedValueOnce(new Error("SMTP error"));

    const result = await runDailyJob(mockConfig);

    expect(mockCleanup).toHaveBeenCalled();
    expect(result.success).toBe(false);
    expect(result.error).toContain("SMTP error");
  });

  test("returns success result with details", async () => {
    const result = await runDailyJob(mockConfig);

    expect(result).toEqual({
      success: true,
      screenshotPaths: ["/tmp/screenshot-0.png", "/tmp/screenshot-1.png"],
      logContent: "Log line 1\nLog line 2\n",
    });
  });
});
