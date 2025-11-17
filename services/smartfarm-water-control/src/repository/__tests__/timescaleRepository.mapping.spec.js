const { TimescaleRepository } = require('../timescaleRepository');

describe('TimescaleRepository mapping', () => {
  function makeRepo() {
    const pool = {
      query: jest.fn()
    };
    const repo = new TimescaleRepository(pool);
    return { repo, pool };
  }

  test('getLatestSensorReading maps time and location aliases', async () => {
    const { repo, pool } = makeRepo();
    pool.query.mockResolvedValueOnce({ rows: [{
      sensor_id: 'WL-1',
      value: '12.5',
      timestamp: new Date('2025-01-01T00:00:00Z'),
      lat: 13.7,
      lng: 100.5
    }] });

    const reading = await repo.getLatestSensorReading('WL-1', 'water_level');
    expect(reading).toEqual({
      sensorId: 'WL-1',
      value: 12.5,
      timestamp: new Date('2025-01-01T00:00:00Z'),
      location: { lat: 13.7, lng: 100.5 },
      type: 'water_level',
      unit: 'cm'
    });
  });

  test('getSensorHistory maps time and location aliases', async () => {
    const { repo, pool } = makeRepo();
    pool.query.mockResolvedValueOnce({ rows: [{
      sensor_id: 'MS-1',
      value: '55.2',
      timestamp: new Date('2025-01-02T00:00:00Z'),
      lat: 13.1,
      lng: 100.9
    }] });

    const rows = await repo.getSensorHistory('MS-1', 'moisture', new Date('2025-01-01'), new Date('2025-01-03'));
    expect(rows[0]).toEqual({
      sensorId: 'MS-1',
      value: 55.2,
      timestamp: new Date('2025-01-02T00:00:00Z'),
      location: { lat: 13.1, lng: 100.9 },
      type: 'moisture',
      unit: '%'
    });
  });
});