import { describe, expect, test, beforeEach, afterEach } from "vitest";
import { loadConfig } from "./config";

describe("loadConfig", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  const validEnv = {
    SMTP_USER: "test@example.com",
    SMTP_PASS: "test-password",
    EMAIL_TO: "recipient@example.com",
    SSH_HOST: "192.168.1.1",
    SSH_USER: "ubuntu",
    SSH_KEY_PATH: "/path/to/key.pem",
    DASHBOARD_MOISTURE_URL: "http://localhost:8080/moisture.html",
    DASHBOARD_WATER_LEVEL_URL: "http://localhost:8080/water.html",
    PM2_LOG_PATH: "~/.pm2/logs/app.log",
  };

  test("throws ConfigError when SMTP_PASS is missing", () => {
    const { SMTP_PASS, ...envWithoutPass } = validEnv;
    Object.assign(process.env, envWithoutPass);

    expect(() => loadConfig()).toThrow(
      "Missing required environment variable: SMTP_PASS",
    );
  });

  test("throws ConfigError when SSH_KEY_PATH is missing", () => {
    const { SSH_KEY_PATH, ...envWithoutKey } = validEnv;
    Object.assign(process.env, envWithoutKey);

    expect(() => loadConfig()).toThrow(
      "Missing required environment variable: SSH_KEY_PATH",
    );
  });

  test("returns default SMTP_HOST and SMTP_PORT when not provided", () => {
    Object.assign(process.env, validEnv);

    const config = loadConfig();

    expect(config.smtp.host).toBe("smtp.gmail.com");
    expect(config.smtp.port).toBe(587);
  });

  test("uses provided SMTP_HOST and SMTP_PORT over defaults", () => {
    const customHost = "smtp.custom.com";
    const customPort = "465";
    Object.assign(process.env, validEnv, {
      SMTP_HOST: customHost,
      SMTP_PORT: customPort,
    });

    const config = loadConfig();

    expect(config.smtp.host).toBe(customHost);
    expect(config.smtp.port).toBe(465);
  });

  test("parses all environment variables into typed config object", () => {
    Object.assign(process.env, validEnv);

    const config = loadConfig();

    expect(config).toEqual({
      smtp: {
        host: "smtp.gmail.com",
        port: 587,
        user: validEnv.SMTP_USER,
        pass: validEnv.SMTP_PASS,
        from: `Munbon Daily Report <${validEnv.SMTP_USER}>`,
      },
      email: {
        to: validEnv.EMAIL_TO,
      },
      ssh: {
        host: validEnv.SSH_HOST,
        port: 22,
        user: validEnv.SSH_USER,
        keyPath: validEnv.SSH_KEY_PATH,
      },
      dashboards: {
        moistureUrl: validEnv.DASHBOARD_MOISTURE_URL,
        waterLevelUrl: validEnv.DASHBOARD_WATER_LEVEL_URL,
      },
      pm2LogPath: validEnv.PM2_LOG_PATH,
      timezone: "Asia/Bangkok",
    });
  });

  test("uses EMAIL_FROM when provided", () => {
    const customFrom = "Custom Sender <custom@example.com>";
    Object.assign(process.env, validEnv, { EMAIL_FROM: customFrom });

    const config = loadConfig();

    expect(config.smtp.from).toBe(customFrom);
  });

  test("uses custom SSH_PORT when provided", () => {
    Object.assign(process.env, validEnv, { SSH_PORT: "2222" });

    const config = loadConfig();

    expect(config.ssh.port).toBe(2222);
  });

  test("uses custom TZ when provided", () => {
    Object.assign(process.env, validEnv, { TZ: "America/New_York" });

    const config = loadConfig();

    expect(config.timezone).toBe("America/New_York");
  });

  test("throws ConfigError when SMTP_PORT is non-numeric string", () => {
    Object.assign(process.env, validEnv, { SMTP_PORT: "abc" });

    expect(() => loadConfig()).toThrow("Invalid numeric value for SMTP_PORT");
  });

  test("throws ConfigError when SSH_PORT is non-numeric string", () => {
    Object.assign(process.env, validEnv, { SSH_PORT: "not-a-number" });

    expect(() => loadConfig()).toThrow("Invalid numeric value for SSH_PORT");
  });

  test("throws ConfigError when port value produces NaN", () => {
    Object.assign(process.env, validEnv, { SMTP_PORT: "NaN" });

    expect(() => loadConfig()).toThrow("Invalid numeric value for SMTP_PORT");
  });
});
