const { MoistureShapeIngest } = require('../moistureShapeIngest');

describe('MoistureShapeIngest.primeMoisturePlotReadings', () => {
  const logger = { info: jest.fn(), warn: jest.fn(), error: jest.fn(), debug: jest.fn() };

  function makeRepos({ mappedIds = [], readings = [] } = {}) {
    const repo = {
      pool: {},
      listMappedSensorsForPlot: jest.fn().mockResolvedValue(mappedIds)
    };
    const timescaleRepo = {
      pool: {},
      getLatestMoistureReadings: jest.fn().mockResolvedValue(readings),
      deleteStaleReadingsForSensor: jest.fn().mockResolvedValue([]),
      upsertSensorPlotReading: jest.fn().mockResolvedValue(undefined)
    };
    return { repo, timescaleRepo };
  }

  test('seeds single-sensor plot reading', async () => {
    const pairs = [{ sensorId: '00000006', plotId: 'SF-L2' }];
    const { repo, timescaleRepo } = makeRepos({
      mappedIds: ['00000006'],
      readings: [
        { sensorId: '00000006', value: 55, timestamp: new Date('2025-10-27T10:00:00Z') }
      ]
    });

    const ingest = new MoistureShapeIngest({ repo, logger, timescaleRepo });
    await ingest.primeMoisturePlotReadings(pairs);

    expect(timescaleRepo.deleteStaleReadingsForSensor).toHaveBeenCalledWith(repo.pool, {
      sensorId: '00000006', sensorType: 'moisture', currentPlotId: 'SF-L2'
    });
    expect(timescaleRepo.upsertSensorPlotReading).toHaveBeenCalledWith(repo.pool, expect.objectContaining({
      plotId: 'SF-L2', sensorId: '00000006', sensorType: 'moisture', value: 55, units: '%'
    }));
  });

  test('averages multiple mapped sensors and records contributors', async () => {
    const pairs = [
      { sensorId: '00000001', plotId: 'SF-U5' },
      { sensorId: '00000002', plotId: 'SF-U5' }
    ];
    const { repo, timescaleRepo } = makeRepos({
      mappedIds: ['00000001', '00000002'],
      readings: [
        { sensorId: '00000001', value: 50, timestamp: new Date('2025-10-27T10:00:00Z') },
        { sensorId: '00000002', value: 70, timestamp: new Date('2025-10-27T10:05:00Z') }
      ]
    });

    const ingest = new MoistureShapeIngest({ repo, logger, timescaleRepo });
    await ingest.primeMoisturePlotReadings(pairs);

    const [, reading] = timescaleRepo.upsertSensorPlotReading.mock.calls[0];
    expect(reading.plotId).toBe('SF-U5');
    expect(reading.sensorId).toBe('AVG_2_sensors');
    expect(reading.value).toBeCloseTo(60, 3);
    expect(reading.contributingSensorIds.sort()).toEqual(['00000001', '00000002']);
  });

  test('skips when no fresh readings', async () => {
    const pairs = [{ sensorId: '00000006', plotId: 'SF-L2' }];
    const { repo, timescaleRepo } = makeRepos({ mappedIds: ['00000006'], readings: [] });

    const ingest = new MoistureShapeIngest({ repo, logger, timescaleRepo });
    await ingest.primeMoisturePlotReadings(pairs);

    expect(timescaleRepo.upsertSensorPlotReading).not.toHaveBeenCalled();
  });
});