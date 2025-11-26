import type { Config } from "./types";

export class ConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConfigError";
  }
}

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new ConfigError(`Missing required environment variable: ${name}`);
  }
  return value;
}

function optionalEnv(name: string, defaultValue: string): string {
  return process.env[name] || defaultValue;
}

function optionalEnvInt(name: string, defaultValue: number): number {
  const value = process.env[name];
  return value ? parseInt(value, 10) : defaultValue;
}

export function loadConfig(): Config {
  const smtpUser = requireEnv("SMTP_USER");
  const smtpPass = requireEnv("SMTP_PASS");
  const emailTo = requireEnv("EMAIL_TO");
  const sshHost = requireEnv("SSH_HOST");
  const sshUser = requireEnv("SSH_USER");
  const sshKeyPath = requireEnv("SSH_KEY_PATH");
  const dashboardMoistureUrl = requireEnv("DASHBOARD_MOISTURE_URL");
  const dashboardWaterLevelUrl = requireEnv("DASHBOARD_WATER_LEVEL_URL");
  const pm2LogPath = requireEnv("PM2_LOG_PATH");

  return {
    smtp: {
      host: optionalEnv("SMTP_HOST", "smtp.gmail.com"),
      port: optionalEnvInt("SMTP_PORT", 587),
      user: smtpUser,
      pass: smtpPass,
      from: optionalEnv("EMAIL_FROM", `Munbon Daily Report <${smtpUser}>`),
    },
    email: {
      to: emailTo,
    },
    ssh: {
      host: sshHost,
      port: optionalEnvInt("SSH_PORT", 22),
      user: sshUser,
      keyPath: sshKeyPath,
    },
    dashboards: {
      moistureUrl: dashboardMoistureUrl,
      waterLevelUrl: dashboardWaterLevelUrl,
    },
    pm2LogPath,
    timezone: optionalEnv("TZ", "Asia/Bangkok"),
  };
}
