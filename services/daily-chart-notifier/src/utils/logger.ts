import pino from "pino";

export const logger = pino({
  name: "daily-chart-notifier",
  level: process.env.LOG_LEVEL || "info",
});
