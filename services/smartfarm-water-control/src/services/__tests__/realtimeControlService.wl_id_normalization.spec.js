const { RealtimeControlService } = require('../realtimeControlService');

describe('RealtimeControlService water_level sensorId preference', () => {
  test('single WL reading stores AWD sensorId instead of legacy id', async () => {
    const logger = { info: jest.fn(), warn: jest.fn(), error: jest.fn(), debug: jest.fn() };
    const repo = {
      pool: {},
      getSensorPlotMapping: jest.fn().mockResolvedValue({ plotId: 'SF-L2', sensorType: 'water_level' }),
      getControlThresholds: jest.fn().mockResolvedValue({
        moistureLowerThreshold: 50,
        moistureUpperThreshold: 69,
        waterLevelLowerThreshold: -10,
        waterLevelUpperThreshold: 10
      }),
      getValveState: jest.fn().mockResolvedValue({ currentState: 'OFF' }),
      deleteStaleReadingsForSensor: jest.fn().mockResolvedValue([]),
      // One fresh mapped reading from AWD-XYZ
      getFreshSensorReadingsForPlot: jest.fn().mockResolvedValue([{ sensorId: 'AWD-XYZ', value: 12, timestamp: new Date() }]),
      upsertSensorPlotReading: jest.fn().mockResolvedValue(undefined),
      logControlDecision: jest.fn().mockResolvedValue(1)
    };
    const valveSvc = { sendValveCommandWithRetry: jest.fn().mockResolvedValue({}) };
    const rcs = new RealtimeControlService(repo, valveSvc, logger, { readingsRepository: repo });

    await rcs.handleSensorReading({ sensorId: 'WL-SF-U1', sensorType: 'water_level', value: 12, timestamp: new Date() });

    const call = repo.upsertSensorPlotReading.mock.calls[0][1];
    expect(call.sensorId).toBe('AWD-XYZ');
  });
});