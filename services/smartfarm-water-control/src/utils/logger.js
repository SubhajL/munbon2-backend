const winston = require("winston");
const path = require("path");

const logLevel = process.env.LOG_LEVEL || "info";

const logger = winston.createLogger({
  level: logLevel,
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json(),
  ),
  defaultMeta: { service: "smartfarm-water-control" },
  transports: [
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.colorize(),
        winston.format.simple(),
      ),
    }),
  ],
});

// Add file transport in production
if (process.env.NODE_ENV === "production") {
  logger.add(
    new winston.transports.File({
      filename: path.join("logs", "error.log"),
      level: "error",
    }),
  );
  logger.add(
    new winston.transports.File({
      filename: path.join("logs", "combined.log"),
    }),
  );
}

module.exports = logger;
