import type { Config, JobResult, Attachment } from "./types";
import { captureScreenshots } from "./screenshot";
import { fetchPm2Logs } from "./log-fetcher";
import { sendEmail } from "./email";
import { createTempWorkspace } from "./utils/temp";
import { logger } from "./utils/logger";

export async function runDailyJob(config: Config): Promise<JobResult> {
  const workspace = createTempWorkspace("munbon-daily-report");

  try {
    logger.info("Starting daily report job");

    const urls = [
      config.dashboards.moistureUrl,
      config.dashboards.waterLevelUrl,
    ];
    logger.info({ urls }, "Capturing dashboard screenshots");
    const screenshotPaths = await captureScreenshots(
      urls,
      workspace.screenshotDir,
    );

    logger.info("Fetching PM2 logs from EC2");
    const logContent = await fetchPm2Logs(config);

    const attachments: Attachment[] = [
      { filename: "moisture-dashboard.png", path: screenshotPaths[0] },
      { filename: "water-level-dashboard.png", path: screenshotPaths[1] },
      { filename: "pm2-logs.txt", content: logContent },
    ];

    logger.info(
      { attachmentCount: attachments.length },
      "Sending daily report email",
    );
    await sendEmail(config, attachments);

    logger.info("Daily report job completed successfully");

    return {
      success: true,
      screenshotPaths,
      logContent,
    };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    logger.error({ error: errorMessage }, "Daily report job failed");

    return {
      success: false,
      error: errorMessage,
    };
  } finally {
    workspace.cleanup();
    logger.info("Cleaned up temp workspace");
  }
}
