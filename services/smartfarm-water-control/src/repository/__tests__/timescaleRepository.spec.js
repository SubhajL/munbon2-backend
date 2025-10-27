const { TimescaleRepository } = require('../timescaleRepository');

describe('getFreshSensorReadingsForPlot', () => {
  let repository;
  let mockPool;

  beforeEach(() => {
    mockPool = {
      query: jest.fn()
    };

    repository = new TimescaleRepository(mockPool, {
      planning: 'ros_gis_smartfarm',
      control: 'water_control_smartfarm'
    });
  });

  test('returns empty array when no sensors mapped to plot', async () => {
    mockPool.query.mockResolvedValueOnce({ rows: [] });

    const result = await repository.getFreshSensorReadingsForPlot(mockPool, {
      plotId: 'P001',
      sensorType: 'moisture'
    });

    expect(result).toEqual([]);
    expect(mockPool.query).toHaveBeenCalledTimes(1);
  });

  test('returns single moisture sensor reading within 30 min window', async () => {
    const now = new Date();

    mockPool.query
      .mockResolvedValueOnce({
        rows: [{ sensor_id: '00000001' }]
      })
      .mockResolvedValueOnce({
        rows: [
          {
            sensor_id: '00000001',
            value: 45.5,
            timestamp: new Date(now.getTime() - 10 * 60 * 1000)
          }
        ]
      });

    const result = await repository.getFreshSensorReadingsForPlot(mockPool, {
      plotId: 'P001',
      sensorType: 'moisture'
    });

    expect(result).toEqual([
      {
        sensorId: '00000001',
        value: 45.5,
        timestamp: expect.any(Date)
      }
    ]);
  });

  test('returns multiple water level sensor readings within 4 hour window', async () => {
    const now = new Date();

    mockPool.query
      .mockResolvedValueOnce({
        rows: [{ sensor_id: '00000001' }, { sensor_id: '00000002' }]
      })
      .mockResolvedValueOnce({
        rows: [
          {
            sensor_id: '00000001',
            value: 25.3,
            timestamp: new Date(now.getTime() - 2 * 60 * 60 * 1000)
          },
          {
            sensor_id: '00000002',
            value: 27.8,
            timestamp: new Date(now.getTime() - 1 * 60 * 60 * 1000)
          }
        ]
      });

    const result = await repository.getFreshSensorReadingsForPlot(mockPool, {
      plotId: 'P001',
      sensorType: 'water_level'
    });

    expect(result).toHaveLength(2);
    expect(result[0].value).toBe(25.3);
    expect(result[1].value).toBe(27.8);
  });

  test('excludes stale readings outside freshness window', async () => {
    const now = new Date();

    mockPool.query
      .mockResolvedValueOnce({
        rows: [
          { sensor_id: '00000001' },
          { sensor_id: '00000002' },
          { sensor_id: '00000003' }
        ]
      })
      .mockResolvedValueOnce({
        rows: [
          {
            sensor_id: '00000001',
            value: 45.0,
            timestamp: new Date(now.getTime() - 10 * 60 * 1000)
          }
        ]
      });

    const result = await repository.getFreshSensorReadingsForPlot(mockPool, {
      plotId: 'P001',
      sensorType: 'moisture'
    });

    expect(result).toHaveLength(1);
    expect(result[0].sensorId).toBe('00000001');
  });

  test('uses correct table and column for moisture sensors', async () => {
    mockPool.query
      .mockResolvedValueOnce({
        rows: [{ sensor_id: '00000001' }]
      })
      .mockResolvedValueOnce({
        rows: []
      });

    await repository.getFreshSensorReadingsForPlot(mockPool, {
      plotId: 'P001',
      sensorType: 'moisture'
    });

    expect(mockPool.query).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining('moisture_readings'),
      expect.any(Array)
    );
    expect(mockPool.query).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining('moisture_surface_pct'),
      expect.any(Array)
    );
  });

  test('uses correct table and column for water level sensors', async () => {
    mockPool.query
      .mockResolvedValueOnce({
        rows: [{ sensor_id: '00000001' }]
      })
      .mockResolvedValueOnce({
        rows: []
      });

    await repository.getFreshSensorReadingsForPlot(mockPool, {
      plotId: 'P001',
      sensorType: 'water_level'
    });

    expect(mockPool.query).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining('water_level_readings'),
      expect.any(Array)
    );
    expect(mockPool.query).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining('water_level_cm'),
      expect.any(Array)
    );
  });
});

describe('upsertSensorPlotReading', () => {
  let repository;
  let mockPool;

  beforeEach(() => {
    mockPool = {
      query: jest.fn()
    };

    repository = new TimescaleRepository(mockPool, {
      planning: 'ros_gis_smartfarm',
      control: 'water_control_smartfarm'
    });
  });

  test('stores single sensor reading with contributing sensor ID', async () => {
    mockPool.query.mockResolvedValueOnce({ rows: [] });

    await repository.upsertSensorPlotReading(mockPool, {
      plotId: 'P001',
      sensorId: '00000001',
      sensorType: 'moisture',
      value: 45.5,
      units: '%',
      timestamp: new Date(),
      contributingSensorIds: ['00000001']
    });

    expect(mockPool.query).toHaveBeenCalledWith(
      expect.stringContaining('contributing_sensor_ids'),
      expect.arrayContaining([
        'P001',
        '00000001',
        'moisture',
        45.5,
        '%',
        expect.any(Date),
        ['00000001']
      ])
    );
  });

  test('stores aggregated reading with multiple contributing sensors', async () => {
    mockPool.query.mockResolvedValueOnce({ rows: [] });

    await repository.upsertSensorPlotReading(mockPool, {
      plotId: 'P001',
      sensorId: 'AVG_3_sensors',
      sensorType: 'water_level',
      value: 26.5,
      units: 'cm',
      timestamp: new Date(),
      contributingSensorIds: ['00000001', '00000002', '00000003']
    });

    expect(mockPool.query).toHaveBeenCalledWith(
      expect.anything(),
      expect.arrayContaining([
        'P001',
        'AVG_3_sensors',
        'water_level',
        26.5,
        'cm',
        expect.any(Date),
        ['00000001', '00000002', '00000003']
      ])
    );
  });

  test('handles null contributing sensor IDs', async () => {
    mockPool.query.mockResolvedValueOnce({ rows: [] });

    await repository.upsertSensorPlotReading(mockPool, {
      plotId: 'P001',
      sensorId: '00000001',
      sensorType: 'moisture',
      value: 45.5,
      units: '%',
      timestamp: new Date()
    });

    expect(mockPool.query).toHaveBeenCalledWith(
      expect.anything(),
      expect.arrayContaining([
        'P001',
        '00000001',
        'moisture',
        45.5,
        '%',
        expect.any(Date),
        null
      ])
    );
  });
});
