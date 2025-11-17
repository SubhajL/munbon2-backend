const winston = require('winston');
const path = require('path');
const util = require('util');

const logLevel = process.env.LOG_LEVEL || 'info';

const consoleFormat = winston.format.printf((info) => {
  const {
    level,
    message,
    timestamp,
    error,
    service: _service,
    ...rawMetadata
  } = info;

  // Filter out winston internal symbols
  const metadata = {};
  for (const key of Object.keys(rawMetadata)) {
    if (typeof key === 'string' && !key.startsWith('Symbol(')) {
      metadata[key] = rawMetadata[key];
    }
  }

  // Build timestamp prefix
  const ts = timestamp ? `[${timestamp}] ` : '';
  let msg = `${ts}${level}: `;

  // Handle message
  if (typeof message === 'string') {
    msg += message;
  } else if (message) {
    msg += util.inspect(message, { depth: 2, colors: false, compact: true });
  }

  // Handle error
  if (error instanceof Error) {
    msg += `\n${error.stack}`;
  } else if (metadata.error instanceof Error) {
    msg += `\n${metadata.error.stack}`;
    delete metadata.error;
  }

  // Handle metadata
  const metaKeys = Object.keys(metadata);
  if (metaKeys.length > 0) {
    msg += ` ${util.inspect(metadata, { depth: 2, colors: false, compact: true })}`;
  }

  return msg;
});

const logger = winston.createLogger({
  level: logLevel,
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true })
  ),
  defaultMeta: { service: 'smartfarm-water-control' },
  transports: [
    new winston.transports.Console({
      format: winston.format.combine(
        consoleFormat,
        winston.format.colorize({ all: true })
      )
    })
  ]
});

// Add file transport in production with JSON format
if (process.env.NODE_ENV === 'production') {
  logger.add(
    new winston.transports.File({
      filename: path.join('logs', 'error.log'),
      level: 'error',
      format: winston.format.json()
    })
  );
  logger.add(
    new winston.transports.File({
      filename: path.join('logs', 'combined.log'),
      format: winston.format.json()
    })
  );
}

module.exports = logger;
