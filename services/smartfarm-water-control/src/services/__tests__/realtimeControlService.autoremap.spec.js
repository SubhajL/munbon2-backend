const { RealtimeControlService } = require('../realtimeControlService');

describe('RealtimeControlService auto-relocation (water_level)', () => {
  const logger = { info: jest.fn(), warn: jest.fn(), error: jest.fn(), debug: jest.fn() };

  function makeRepo(overrides = {}) {
    return {
      pool: {},
      getSensorPlotMapping: jest.fn().mockResolvedValue(null),
      upsertSensorPlotMapping: jest.fn().mockResolvedValue('SF-B'),
      getControlThresholds: jest.fn().mockResolvedValue({
        plotId: 'SF-B',
        moistureLowerThreshold: 40,
        moistureUpperThreshold: 70,
        waterLevelLowerThreshold: -10,
        waterLevelUpperThreshold: 10
      }),
      getValveState: jest.fn().mockResolvedValue({ currentState: 'OFF', lastChangedAt: null, lastChangeReason: null }),
      deleteStaleReadingsForSensor: jest.fn().mockResolvedValue([]),
      getFreshSensorReadingsForPlot: jest.fn().mockResolvedValue([]),
      upsertSensorPlotReading: jest.fn().mockResolvedValue(undefined),
      logControlDecision: jest.fn().mockResolvedValue({ id: 1 }),
      ...overrides
    };
  }

  test('updates mapping when GPS resolves to different plot', async () => {
    const repo = makeRepo({
      getSensorPlotMapping: jest
        .fn()
        .mockResolvedValueOnce({ plotId: 'SF-A', sensorType: 'water_level' }) // existing mapping
        .mockResolvedValueOnce({ plotId: 'SF-B', sensorType: 'water_level' }) // after update
    });

    const geoSpatialResolver = {
      resolvePlotFromCoordinates: jest.fn().mockResolvedValue('SF-B')
    };

    const svc = new RealtimeControlService(
      repo,
      { sendValveCommandWithRetry: jest.fn().mockResolvedValue({}) },
      logger,
      { readingsRepository: repo, geoSpatialResolver }
    );

    // Call the new helper directly to keep test focused
    const result = await svc.ensureWaterLevelMappingFromCoordinates({
      sensorId: '00000001',
      locationLat: 14.5,
      locationLng: 102.15
    });

    expect(geoSpatialResolver.resolvePlotFromCoordinates).toHaveBeenCalledWith(102.15, 14.5, 'water_level');
    expect(repo.upsertSensorPlotMapping).toHaveBeenCalledWith(repo.pool, {
      sensorId: '00000001',
      plotId: 'SF-B',
      sensorType: 'water_level'
    });
    expect(result).toEqual({ changed: true, plotId: 'SF-B', previousPlotId: 'SF-A' });
  });

  test('no update when resolved plot equals existing', async () => {
    const repo = makeRepo({
      getSensorPlotMapping: jest.fn().mockResolvedValue({ plotId: 'SF-X', sensorType: 'water_level' })
    });
    const geoSpatialResolver = {
      resolvePlotFromCoordinates: jest.fn().mockResolvedValue('SF-X')
    };
    const svc = new RealtimeControlService(
      repo,
      { sendValveCommandWithRetry: jest.fn().mockResolvedValue({}) },
      logger,
      { readingsRepository: repo, geoSpatialResolver }
    );

    const result = await svc.ensureWaterLevelMappingFromCoordinates({
      sensorId: '00000002',
      locationLat: 14.6,
      locationLng: 102.16
    });

    expect(repo.upsertSensorPlotMapping).not.toHaveBeenCalled();
    expect(result).toEqual({ changed: false, plotId: 'SF-X', previousPlotId: 'SF-X' });
  });

  test('no update when coords missing', async () => {
    const repo = makeRepo();
    const geoSpatialResolver = {
      resolvePlotFromCoordinates: jest.fn()
    };
    const svc = new RealtimeControlService(
      repo,
      { sendValveCommandWithRetry: jest.fn().mockResolvedValue({}) },
      logger,
      { readingsRepository: repo, geoSpatialResolver }
    );

    const result = await svc.ensureWaterLevelMappingFromCoordinates({
      sensorId: '00000003',
      locationLat: null,
      locationLng: undefined
    });

    expect(geoSpatialResolver.resolvePlotFromCoordinates).not.toHaveBeenCalled();
    expect(repo.upsertSensorPlotMapping).not.toHaveBeenCalled();
    expect(result).toEqual({ changed: false, plotId: null, previousPlotId: null });
  });
});