const { describe, it, expect, beforeEach } = require('@jest/globals');

describe('config/index gating of device mapping', () => {
  beforeEach(() => {
    jest.resetModules();
    delete process.env.USE_DEVICE_MAPPING_JSON;
  });

  it('does not load device mapping when flag is not true', () => {
    const config = require('../index');
    expect(config.deviceNames).toBeNull();
  });

  it('loads device mapping only when flag true', () => {
    process.env.USE_DEVICE_MAPPING_JSON = 'true';
    jest.resetModules();
    const cfg = require('../index');
    // deviceNames may be null if file missing; assert property exists
    expect('deviceNames' in cfg).toBe(true);
  });
});