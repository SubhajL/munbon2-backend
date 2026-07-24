import { describe, expect, test } from 'vitest';
import { ConfigError, loadConfig } from './config';

const withHost = (extra: Record<string, string> = {}) => ({
  MODBUS_HOST: '127.0.0.1',
  JWT_SECRET: 'test-secret',
  ...extra,
});

describe('loadConfig', () => {
  test('requires MODBUS_HOST (fails fast rather than polling a default host)', () => {
    expect(() => loadConfig({ JWT_SECRET: 's' })).toThrow(ConfigError);
  });

  test('requires JWT_SECRET (needed to verify auth tokens)', () => {
    expect(() => loadConfig({ MODBUS_HOST: '127.0.0.1' })).toThrow(ConfigError);
  });

  test('applies auth issuer/audience defaults', () => {
    const cfg = loadConfig(withHost());
    expect(cfg.auth).toEqual({
      jwtSecret: 'test-secret',
      jwtIssuer: 'munbon-auth',
      jwtAudience: 'munbon-api',
    });
  });

  test('defaults rate limit and disallows in-memory audit by default', () => {
    const cfg = loadConfig(withHost());
    expect(cfg.httpHost).toBe('0.0.0.0');
    expect(cfg.rateLimit).toEqual({ windowMs: 60_000, max: 30 });
    expect(cfg.allowInMemoryAudit).toBe(false);
    expect(cfg.allowMachineCommands).toBe(false);
  });

  test('accepts a loopback-only HTTP bind host', () => {
    expect(loadConfig(withHost({ HTTP_HOST: '127.0.0.1' })).httpHost).toBe('127.0.0.1');
  });

  test('ALLOW_MACHINE_COMMANDS accepts only explicit true or false', () => {
    expect(
      loadConfig(
        withHost({
          ALLOW_MACHINE_COMMANDS: 'true',
          DATABASE_URL: 'postgresql://scada:secret@127.0.0.1/scada',
          SCADA_SITE_CANONICAL_GATE_ID: 'M(0,0;1,0)',
          SCADA_APPROVED_FIELD_BUNDLE_PATH: '/approved/field-bundle.json',
        }),
      ).allowMachineCommands,
    ).toBe(true);
    expect(loadConfig(withHost({ ALLOW_MACHINE_COMMANDS: 'false' })).allowMachineCommands).toBe(
      false,
    );
    expect(() => loadConfig(withHost({ ALLOW_MACHINE_COMMANDS: '1' }))).toThrow(ConfigError);
    expect(() => loadConfig(withHost({ ALLOW_MACHINE_COMMANDS: 'TRUE' }))).toThrow(ConfigError);
  });

  test('machine commands require the durable Postgres reservation store', () => {
    expect(() =>
      loadConfig(
        withHost({
          ALLOW_MACHINE_COMMANDS: 'true',
          ALLOW_IN_MEMORY_AUDIT: 'true',
        }),
      ),
    ).toThrow(/DATABASE_URL is required when ALLOW_MACHINE_COMMANDS=true/);
    expect(
      loadConfig(
        withHost({
          ALLOW_MACHINE_COMMANDS: 'true',
          DATABASE_URL: 'postgresql://scada:secret@127.0.0.1/scada',
          SCADA_SITE_CANONICAL_GATE_ID: 'M(0,0;1,0)',
          SCADA_APPROVED_FIELD_BUNDLE_PATH: '/approved/field-bundle.json',
        }),
      ).allowMachineCommands,
    ).toBe(true);
  });

  test('machine commands require the local canonical gate and rich approved field bundle', () => {
    const durable = {
      ALLOW_MACHINE_COMMANDS: 'true',
      DATABASE_URL: 'postgresql://scada:secret@127.0.0.1/scada',
    };
    expect(() => loadConfig(withHost(durable))).toThrow(/SCADA_SITE_CANONICAL_GATE_ID/);
    expect(() =>
      loadConfig(withHost({ ...durable, SCADA_SITE_CANONICAL_GATE_ID: 'M(0,0;1,0)' })),
    ).toThrow(/SCADA_APPROVED_FIELD_BUNDLE_PATH/);
  });

  test('machine boot rejects legacy split artifacts without the rich bundle', () => {
    expect(() =>
      loadConfig(
        withHost({
          ALLOW_MACHINE_COMMANDS: 'true',
          DATABASE_URL: 'postgresql://scada:secret@127.0.0.1/scada',
          SCADA_SITE_CANONICAL_GATE_ID: 'M(0,0;1,0)',
          SCADA_DEVICE_REGISTRY_PATH: '/legacy/registry.json',
          SCADA_APPROVED_LINEAGE_ANCHOR_PATH: '/legacy/lineage.json',
        }),
      ),
    ).toThrow(/SCADA_APPROVED_FIELD_BUNDLE_PATH/);
  });

  test('ALLOW_IN_MEMORY_AUDIT=true enables the in-memory sink flag', () => {
    expect(loadConfig(withHost({ ALLOW_IN_MEMORY_AUDIT: 'true' })).allowInMemoryAudit).toBe(true);
  });

  test('service auth is null (dark) when SCHEDULER_SERVICE_JWT_SECRET is unset', () => {
    expect(loadConfig(withHost()).serviceAuth).toBeNull();
  });

  test('service auth uses scheduler/machine-boundary defaults when only the secret is set', () => {
    expect(
      loadConfig(withHost({ SCHEDULER_SERVICE_JWT_SECRET: 'svc-secret' })).serviceAuth,
    ).toEqual({
      secret: 'svc-secret',
      issuer: 'munbon-scheduler',
      audience: 'munbon-scada-machine-boundary',
      maxAge: '5m',
    });
  });

  test('rejects a malformed SCHEDULER_SERVICE_JWT_MAX_AGE (fail closed, not a disabled policy)', () => {
    expect(() =>
      loadConfig(
        withHost({
          SCHEDULER_SERVICE_JWT_SECRET: 'svc-secret',
          SCHEDULER_SERVICE_JWT_MAX_AGE: 'abc',
        }),
      ),
    ).toThrow(ConfigError);
  });

  test('accepts a valid duration override for the service-token maxAge', () => {
    expect(
      loadConfig(
        withHost({ SCHEDULER_SERVICE_JWT_SECRET: 's', SCHEDULER_SERVICE_JWT_MAX_AGE: '90s' }),
      ).serviceAuth?.maxAge,
    ).toBe('90s');
  });

  test('service auth issuer/audience/maxAge are overridable from env', () => {
    const cfg = loadConfig(
      withHost({
        SCHEDULER_SERVICE_JWT_SECRET: 'svc-secret',
        SCHEDULER_SERVICE_JWT_ISSUER: 'iss-x',
        SCHEDULER_SERVICE_JWT_AUDIENCE: 'aud-x',
        SCHEDULER_SERVICE_JWT_MAX_AGE: '2m',
      }),
    );
    expect(cfg.serviceAuth).toEqual({
      secret: 'svc-secret',
      issuer: 'iss-x',
      audience: 'aud-x',
      maxAge: '2m',
    });
  });

  test('applies defaults for everything but the required host', () => {
    const cfg = loadConfig(withHost());
    expect(cfg.modbus).toEqual({
      host: '127.0.0.1',
      port: 502,
      unitId: 1,
      timeoutMs: 2_000,
      pollIntervalMs: 3_000,
    });
    expect(cfg.freshness).toEqual({ staleAfterMs: 10_000, offlineAfterMs: 20_000 });
    expect(cfg.site).toEqual({ gateId: 'waste-way', name: 'Waste Way' });
  });

  test('overrides from env are parsed as integers', () => {
    const cfg = loadConfig(
      withHost({ MODBUS_HOST: '10.0.0.5', MODBUS_PORT: '5020', MODBUS_UNIT_ID: '7' }),
    );
    expect([cfg.modbus.host, cfg.modbus.port, cfg.modbus.unitId]).toEqual(['10.0.0.5', 5020, 7]);
  });

  test('rejects a non-integer numeric env', () => {
    expect(() => loadConfig(withHost({ MODBUS_PORT: 'abc' }))).toThrow(ConfigError);
  });

  test('rejects stale threshold >= offline threshold', () => {
    expect(() =>
      loadConfig(withHost({ MODBUS_STALE_AFTER_MS: '20000', MODBUS_OFFLINE_AFTER_MS: '20000' })),
    ).toThrow(ConfigError);
  });

  describe('poll interval is constrained to the spec window 2000-5000ms', () => {
    test.each(['2000', '3000', '5000'])('accepts %s', (interval) => {
      expect(
        loadConfig(withHost({ MODBUS_POLL_INTERVAL_MS: interval })).modbus.pollIntervalMs,
      ).toBe(Number(interval));
    });

    test.each(['1999', '5001', '0', '60000'])('rejects %s', (interval) => {
      expect(() => loadConfig(withHost({ MODBUS_POLL_INTERVAL_MS: interval }))).toThrow(
        ConfigError,
      );
    });
  });
});
