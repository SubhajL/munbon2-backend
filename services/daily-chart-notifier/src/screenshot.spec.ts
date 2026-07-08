import { describe, expect, test, vi, beforeEach, afterEach } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { captureScreenshots } from "./screenshot";

vi.mock("puppeteer", () => {
  const mockPage = {
    goto: vi.fn().mockResolvedValue(undefined),
    waitForNetworkIdle: vi.fn().mockResolvedValue(undefined),
    waitForTimeout: vi.fn().mockResolvedValue(undefined),
    screenshot: vi.fn().mockResolvedValue(Buffer.from("fake-image")),
    close: vi.fn().mockResolvedValue(undefined),
    setViewport: vi.fn().mockResolvedValue(undefined),
  };

  const mockBrowser = {
    newPage: vi.fn().mockResolvedValue(mockPage),
    close: vi.fn().mockResolvedValue(undefined),
  };

  return {
    default: {
      launch: vi.fn().mockResolvedValue(mockBrowser),
    },
  };
});

describe("captureScreenshots", () => {
  let tempDir: string;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(
      path.join(require("os").tmpdir(), "screenshot-test-"),
    );
    vi.clearAllMocks();
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  test("returns array of screenshot file paths", async () => {
    const urls = [
      "http://localhost:8080/page1.html",
      "http://localhost:8080/page2.html",
    ];

    const result = await captureScreenshots(urls, tempDir);

    expect(result).toHaveLength(2);
    expect(result[0]).toContain("screenshot-0.png");
    expect(result[1]).toContain("screenshot-1.png");
  });

  test("launches browser with no-sandbox args", async () => {
    const puppeteer = await import("puppeteer");
    const urls = ["http://localhost:8080/page.html"];

    await captureScreenshots(urls, tempDir);

    expect(puppeteer.default.launch).toHaveBeenCalledWith(
      expect.objectContaining({
        args: expect.arrayContaining([
          "--no-sandbox",
          "--disable-setuid-sandbox",
        ]),
      }),
    );
  });

  test("visits each URL and waits for network idle", async () => {
    const puppeteer = await import("puppeteer");
    const mockBrowser = await puppeteer.default.launch();
    const mockPage = await mockBrowser.newPage();
    const urls = [
      "http://localhost:8080/page1.html",
      "http://localhost:8080/page2.html",
    ];

    await captureScreenshots(urls, tempDir);

    expect(mockPage.goto).toHaveBeenCalledTimes(2);
    expect(mockPage.goto).toHaveBeenCalledWith(
      urls[0],
      expect.objectContaining({ waitUntil: "networkidle0" }),
    );
    expect(mockPage.goto).toHaveBeenCalledWith(
      urls[1],
      expect.objectContaining({ waitUntil: "networkidle0" }),
    );
  });

  test("takes full page screenshots", async () => {
    const puppeteer = await import("puppeteer");
    const mockBrowser = await puppeteer.default.launch();
    const mockPage = await mockBrowser.newPage();
    const urls = ["http://localhost:8080/page.html"];

    await captureScreenshots(urls, tempDir);

    expect(mockPage.screenshot).toHaveBeenCalledWith(
      expect.objectContaining({
        fullPage: true,
        path: expect.stringContaining("screenshot-0.png"),
      }),
    );
  });

  test("closes browser after completion", async () => {
    const puppeteer = await import("puppeteer");
    const mockBrowser = await puppeteer.default.launch();
    const urls = ["http://localhost:8080/page.html"];

    await captureScreenshots(urls, tempDir);

    expect(mockBrowser.close).toHaveBeenCalled();
  });

  test("closes browser even on error", async () => {
    const puppeteer = await import("puppeteer");
    const mockBrowser = await puppeteer.default.launch();
    const mockPage = await mockBrowser.newPage();
    mockPage.goto.mockRejectedValueOnce(new Error("Navigation failed"));

    const urls = ["http://localhost:8080/page.html"];

    await expect(captureScreenshots(urls, tempDir)).rejects.toThrow(
      "Navigation failed",
    );
    expect(mockBrowser.close).toHaveBeenCalled();
  });
});
