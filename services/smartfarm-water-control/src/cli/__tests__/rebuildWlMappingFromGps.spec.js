const { rebuildWlMappingFromGps } = require('../rebuildWlMappingFromGps');

describe('rebuildWlMappingFromGps', () => {
  test('maps latest AWD coords to plots and upserts', async () => {
    const tsRepo = {
      getLatestWLGpsPerSensor: jest.fn().mockResolvedValue([
        { sensor_id: 'AWD-1', location_lat: 14.49, location_lng: 102.15 },
        { sensor_id: 'AWD-2', location_lat: 14.50, location_lng: 102.16 }
      ])
    };
    const cfgRepo = {
      pool: {},
      findPlotByCoordinates: jest.fn()
        .mockResolvedValueOnce('SF-L2')
        .mockResolvedValueOnce('SF-U5'),
      upsertWLSensorMapping: jest.fn().mockResolvedValue(undefined),
      deleteLegacyWLSfMappings: jest.fn().mockResolvedValue(6)
    };

    const summary = await rebuildWlMappingFromGps({ tsRepo, cfgRepo, maxSensors: 100, dryRun: false, logger: { info: jest.fn() } });

    expect(cfgRepo.findPlotByCoordinates).toHaveBeenCalledTimes(2);
    expect(cfgRepo.upsertWLSensorMapping).toHaveBeenCalledWith({ sensorId: 'AWD-1', plotId: 'SF-L2' });
    expect(cfgRepo.upsertWLSensorMapping).toHaveBeenCalledWith({ sensorId: 'AWD-2', plotId: 'SF-U5' });
    expect(summary.deletedLegacy).toBe(6);
    expect(summary.mapped).toBe(2);
  });

  test('dry-run does not upsert or delete', async () => {
    const tsRepo = { getLatestWLGpsPerSensor: jest.fn().mockResolvedValue([]) };
    const cfgRepo = {
      pool: {},
      findPlotByCoordinates: jest.fn(),
      upsertWLSensorMapping: jest.fn(),
      deleteLegacyWLSfMappings: jest.fn()
    };

    const summary = await rebuildWlMappingFromGps({ tsRepo, cfgRepo, dryRun: true, logger: { info: jest.fn() } });
    expect(cfgRepo.upsertWLSensorMapping).not.toHaveBeenCalled();
    expect(cfgRepo.deleteLegacyWLSfMappings).not.toHaveBeenCalled();
    expect(summary.upserts).toBe(0);
  });
});