import puppeteer from "puppeteer";
import * as path from "path";
import { logger } from "./utils/logger";

const CHART_RENDER_WAIT_MS = 3000;
const NAVIGATION_TIMEOUT_MS = 60000;

export async function captureScreenshots(
  urls: string[],
  outputDir: string,
): Promise<string[]> {
  const browser = await puppeteer.launch({
    headless: true,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu",
    ],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });

    const screenshotPaths: string[] = [];

    for (let i = 0; i < urls.length; i++) {
      const url = urls[i];
      const screenshotPath = path.join(outputDir, `screenshot-${i}.png`);

      logger.info({ url, index: i }, "Navigating to URL");

      await page.goto(url, {
        waitUntil: "networkidle0",
        timeout: NAVIGATION_TIMEOUT_MS,
      });

      await page.waitForTimeout(CHART_RENDER_WAIT_MS);

      await page.screenshot({
        path: screenshotPath,
        fullPage: true,
      });

      logger.info({ screenshotPath }, "Screenshot captured");
      screenshotPaths.push(screenshotPath);
    }

    await page.close();
    return screenshotPaths;
  } finally {
    await browser.close();
  }
}
