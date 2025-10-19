const { describe, it, expect, beforeEach } = require('@jest/globals');
const { WaterLevelLocationListener } = require('../waterLevelLocationListener');

describe('WL LISTEN notify handler', () => {
  it('upserts on valid JSON payload', async () => {
    const l = new WaterLevelLocationListener({ sensorDbPool: {}, configDbPool: { query: jest.fn() }, logger: console });
    await l._handleNotify(JSON.stringify({ sensor_id: 'WL-ABC', lng: 100.1, lat: 13.7 }));
    expect(l.configDb.query).toHaveBeenCalled();
  });

  it('ignores bad json', async () => {
    const l = new WaterLevelLocationListener({ sensorDbPool: {}, configDbPool: { query: jest.fn() }, logger: console });
    await l._handleNotify('{bad');
    expect(l.configDb.query).not.toHaveBeenCalled();
  });

  it('ignores missing coords', async () => {
    const l = new WaterLevelLocationListener({ sensorDbPool: {}, configDbPool: { query: jest.fn() }, logger: console });
    await l._handleNotify(JSON.stringify({ sensor_id: 'WL-ABC', lng: null, lat: 1 }));
    expect(l.configDb.query).not.toHaveBeenCalled();
  });
});