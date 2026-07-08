import "dotenv/config";
import cron from "node-cron";
import { loadConfig } from "./config";
import { runDailyJob } from "./runner";
import { logger } from "./utils/logger";

const CRON_SCHEDULE = "0 13 * * *"; // Daily at 1:00 PM

async function main(): Promise<void> {
  try {
    const config = loadConfig();
    logger.info({ timezone: config.timezone }, "Configuration loaded");

    cron.schedule(
      CRON_SCHEDULE,
      async () => {
        logger.info("Scheduled job triggered");
        const result = await runDailyJob(config);
        if (result.success) {
          logger.info("Scheduled job completed successfully");
        } else {
          logger.error({ error: result.error }, "Scheduled job failed");
        }
      },
      {
        timezone: config.timezone,
      },
    );

    logger.info(
      { schedule: CRON_SCHEDULE, timezone: config.timezone },
      "Daily report scheduler started",
    );

    if (process.env.RUN_IMMEDIATELY === "true") {
      logger.info("RUN_IMMEDIATELY enabled, executing job now");
      const result = await runDailyJob(config);
      if (!result.success) {
        logger.error({ error: result.error }, "Immediate job execution failed");
        process.exit(1);
      }
    }
  } catch (error) {
    logger.error({ error }, "Failed to start scheduler");
    process.exit(1);
  }
}

main();

export { runDailyJob, loadConfig };
