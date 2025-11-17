const { SensorDataService } = require('../sensorDataService');

describe('SensorDataService moisture layer', () => {
  test('passes layer to repository and caches per-layer', async () => {
    const calls = [];
    const mockRepo = {
      getLatestMoistureReading: jest.fn(async (id, layer) => {
        calls.push({ id, layer });
        return { sensorId: id, timestamp: new Date(), type: 'moisture', value: layer === 'deep' ? 44 : 33, unit: '%', depth: 30 };
      })
    };
    const svc = new SensorDataService({ timescaleRepository: mockRepo });

    const r1 = await svc.getSensorReading('MS-0001', { moistureLayer: 'surface' });
    const r2 = await svc.getSensorReading('MS-0001', { moistureLayer: 'deep' });
    const r3 = await svc.getSensorReading('MS-0001', { moistureLayer: 'deep' }); // cached

    expect(calls.map(c => c.layer)).toEqual(['surface', 'deep']);
    expect(r1.value).toBe(33);
    expect(r2.value).toBe(44);
    expect(r3.value).toBe(44);
  });
});