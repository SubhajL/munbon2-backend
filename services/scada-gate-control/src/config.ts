/**
 * Configuration loader. All fields have safe defaults so the service boots
 * without a .env (the field PLC just shows as offline until reachable).
 * Validation fails fast on incoherent values.
 */
import { DEFAULT_UNIT_ID } from './domain/registers';
import type { FreshnessThresholds } from './state/freshness';
import type { ModbusConnectionConfig } from './transport/modbus-serial-transport';

export class ConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ConfigError';
  }
}

export type AppConfig = {
  readonly logLevel: string;
  readonly timezone: string;
  readonly httpPort: number;
  readonly site: { readonly gateId: string; readonly name: string };
  readonly modbus: ModbusConnectionConfig & { readonly pollIntervalMs: number };
  readonly freshness: FreshnessThresholds;
  readonly auth: {
    readonly jwtSecret: string;
    readonly jwtIssuer: string;
    readonly jwtAudience: string;
  };
  /** Postgres connection string for the audit log; empty -> in-memory (dev only). */
  readonly databaseUrl: string;
  /** Allow the non-persistent in-memory audit sink when DATABASE_URL is unset. */
  readonly allowInMemoryAudit: boolean;
  readonly rateLimit: { readonly windowMs: number; readonly max: number };
};

function optionalEnv(env: NodeJS.ProcessEnv, name: string, fallback: string): string {
  const value = env[name];
  return value === undefined || value === '' ? fallback : value;
}

function optionalEnvInt(env: NodeJS.ProcessEnv, name: string, fallback: number): number {
  const raw = env[name];
  if (raw === undefined || raw === '') return fallback;
  const parsed = Number(raw);
  if (!Number.isInteger(parsed)) {
    throw new ConfigError(`Invalid integer for ${name}: "${raw}"`);
  }
  return parsed;
}

function requireEnv(env: NodeJS.ProcessEnv, name: string): string {
  const value = env[name];
  if (value === undefined || value === '') {
    throw new ConfigError(`Missing required environment variable: ${name}`);
  }
  return value;
}

/** Spec: poll field equipment every 2-5 seconds. */
const MIN_POLL_INTERVAL_MS = 2_000;
const MAX_POLL_INTERVAL_MS = 5_000;

export function loadConfig(env: NodeJS.ProcessEnv = process.env): AppConfig {
  const staleAfterMs = optionalEnvInt(env, 'MODBUS_STALE_AFTER_MS', 10_000);
  const offlineAfterMs = optionalEnvInt(env, 'MODBUS_OFFLINE_AFTER_MS', 20_000);
  if (staleAfterMs >= offlineAfterMs) {
    throw new ConfigError(
      `MODBUS_STALE_AFTER_MS (${staleAfterMs}) must be less than MODBUS_OFFLINE_AFTER_MS (${offlineAfterMs})`,
    );
  }
  const pollIntervalMs = optionalEnvInt(env, 'MODBUS_POLL_INTERVAL_MS', 3_000);
  if (pollIntervalMs < MIN_POLL_INTERVAL_MS || pollIntervalMs > MAX_POLL_INTERVAL_MS) {
    throw new ConfigError(
      `MODBUS_POLL_INTERVAL_MS must be between ${MIN_POLL_INTERVAL_MS} and ${MAX_POLL_INTERVAL_MS} ms (spec: 2-5s), got ${pollIntervalMs}`,
    );
  }

  return {
    logLevel: optionalEnv(env, 'LOG_LEVEL', 'info'),
    timezone: optionalEnv(env, 'TZ', 'Asia/Bangkok'),
    httpPort: optionalEnvInt(env, 'PORT', 3030),
    site: {
      gateId: optionalEnv(env, 'SITE_GATE_ID', 'waste-way'),
      name: optionalEnv(env, 'SITE_NAME', 'Waste Way'),
    },
    modbus: {
      // Required: no default, so a misconfigured deploy fails fast instead of
      // silently polling the wrong host. (Spec lists 172.16.1.110; confirm the
      // actual Tailscale-routed endpoint before go-live.)
      host: requireEnv(env, 'MODBUS_HOST'),
      port: optionalEnvInt(env, 'MODBUS_PORT', 502),
      unitId: optionalEnvInt(env, 'MODBUS_UNIT_ID', DEFAULT_UNIT_ID),
      timeoutMs: optionalEnvInt(env, 'MODBUS_TIMEOUT_MS', 2_000),
      pollIntervalMs,
    },
    freshness: { staleAfterMs, offlineAfterMs },
    auth: {
      jwtSecret: requireEnv(env, 'JWT_SECRET'),
      jwtIssuer: optionalEnv(env, 'JWT_ISSUER', 'munbon-auth'),
      jwtAudience: optionalEnv(env, 'JWT_AUDIENCE', 'munbon-api'),
    },
    databaseUrl: optionalEnv(env, 'DATABASE_URL', ''),
    allowInMemoryAudit: optionalEnv(env, 'ALLOW_IN_MEMORY_AUDIT', 'false') === 'true',
    rateLimit: {
      windowMs: optionalEnvInt(env, 'COMMAND_RATE_WINDOW_MS', 60_000),
      max: optionalEnvInt(env, 'COMMAND_RATE_MAX', 30),
    },
  };
}
