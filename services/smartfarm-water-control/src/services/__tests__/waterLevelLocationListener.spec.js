const { describe, it, expect, beforeEach } = require('@jest/globals');
const { WaterLevelLocationListener } = require('../waterLevelLocationListener');

describe('WaterLevelLocationListener', () => {
  let sensorDb, configDb, logger;
  beforeEach(() => {
    sensorDb = { query: jest.fn().mockResolvedValue({ rows: [ { device_id: 'WL-SF-L1', lng: 102.15, lat: 14.49 } ] }) };
    configDb = { query: jest.fn().mockResolvedValue({}) };
    logger = { info: jest.fn(), error: jest.fn() };
  });

  it('processOnce upserts latest WL sensor coords', async () => {
    const l = new WaterLevelLocationListener({ sensorDbPool: sensorDb, configDbPool: configDb, logger });
    await l.processOnce();
    expect(sensorDb.query).toHaveBeenCalled();
    const [sql, params] = configDb.query.mock.calls[0];
    expect(sql).toMatch(/INSERT INTO ros_gis_smartfarm\.sensor_locations/);
    expect(params).toEqual(['WL-SF-L1', 102.15, 14.49]);
  });
});