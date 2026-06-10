import { describe, expect, test } from 'vitest';
import { ConfigError, loadConfig } from './config';

const withHost = (extra: Record<string, string> = {}) => ({ MODBUS_HOST: '127.0.0.1', ...extra });

describe('loadConfig', () => {
  test('requires MODBUS_HOST (fails fast rather than polling a default host)', () => {
    expect(() => loadConfig({})).toThrow(ConfigError);
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
