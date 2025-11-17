const { MoistureShapeIngest } = require('../moistureShapeIngest');

describe('MoistureShapeIngest autoMapMoistureSensors', () => {
  function makeRepo(overrides = {}) {
return {
      pool: {},
      upsertSensorLocation: jest.fn().mockResolvedValue(undefined),
      findPlotByCoordinates: jest.fn().mockResolvedValue(null),
      upsertSensorMapping: jest.fn().mockResolvedValue(undefined),
      ...overrides
    };
  }

  test('creates mapping when point inside a plot', async () => {
    const repo = makeRepo({ findPlotByCoordinates: jest.fn().mockResolvedValue('SF-L2') });
    const ingest = new MoistureShapeIngest({ repo, logger: console });

    const records = [
      { deviceId: '00000006', deviceName: 'H-P1-00000006', lng: 102.149, lat: 14.495 }
    ];

const result = await ingest.autoMapMoistureSensors(records);

expect(repo.findPlotByCoordinates).toHaveBeenCalledWith(repo.pool, 102.149, 14.495);
expect(repo.upsertSensorMapping).toHaveBeenCalledWith({ sensorId: '00000006', plotId: 'SF-L2', sensorType: 'moisture' });
expect(result.stats).toEqual({ processed: 1, mapped: 1, updated: 1, skipped: 0 });
expect(result.pairs).toEqual([{ sensorId: '00000006', plotId: 'SF-L2' }]);
  });

  test('skips mapping when point outside all plots', async () => {
    const repo = makeRepo({ findPlotByCoordinates: jest.fn().mockResolvedValue(null) });
    const ingest = new MoistureShapeIngest({ repo, logger: console });

    const records = [
      { deviceId: '00000001', deviceName: 'H-P3-00000001', lng: 0.0, lat: 0.0 }
    ];

const result = await ingest.autoMapMoistureSensors(records);

expect(repo.upsertSensorMapping).not.toHaveBeenCalled();
expect(result.stats).toEqual({ processed: 1, mapped: 0, updated: 0, skipped: 1 });
expect(result.pairs).toEqual([]);
  });

  test('updates existing mapping when sensor moved plots', async () => {
    const repo = makeRepo({
      findPlotByCoordinates: jest.fn().mockResolvedValue('SF-U5'),
      // simulate idempotent upsert; we track calls only
      upsertSensorMapping: jest.fn().mockResolvedValue(undefined)
    });
    const ingest = new MoistureShapeIngest({ repo, logger: console });

    const records = [
      { deviceId: '00000002', deviceName: 'H-P3-00000002', lng: 102.1503, lat: 14.4968 }
    ];

const result = await ingest.autoMapMoistureSensors(records);

expect(repo.upsertSensorMapping).toHaveBeenCalledWith({ sensorId: '00000002', plotId: 'SF-U5', sensorType: 'moisture' });
expect(result.stats).toEqual({ processed: 1, mapped: 1, updated: 1, skipped: 0 });
expect(result.pairs).toEqual([{ sensorId: '00000002', plotId: 'SF-U5' }]);
  });
});