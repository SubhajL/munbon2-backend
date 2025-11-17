const { SensorUpdateListener } = require('../sensorUpdateListener');
const { RealtimeControlService } = require('../realtimeControlService');

/**
 * E2E-like test starting from EXACT sensor notification payload (LISTEN/NOTIFY),
 * then through RealtimeControlService to SCADA.
 */

describe('E2E moisture from NOTIFY payload → control → SCADA (mocked)', () => {
  const logger = { info: jest.fn(), warn: jest.fn(), error: jest.fn(), debug: jest.fn() };

  function makeRepo() {
    const mappings = new Map([
      ['00000010', { plotId: 'SF-U5', sensorType: 'moisture' }],
      ['00000002', { plotId: 'SF-L2', sensorType: 'moisture' }],
      ['00000004', { plotId: 'SF-L3', sensorType: 'moisture' }]
    ]);

    const thresholds = {
      moistureLowerThreshold: 50,
      moistureUpperThreshold: 69,
      waterLevelLowerThreshold: -10,
      waterLevelUpperThreshold: 10
    };

    return {
      pool: {},
      getSensorPlotMapping: jest.fn(async (_db, sid) => mappings.get(sid)),
      getControlThresholds: jest.fn().mockResolvedValue(thresholds),
      getValveState: jest.fn().mockResolvedValue({ currentState: 'OFF' }),
      deleteStaleReadingsForSensor: jest.fn().mockResolvedValue([]),
      getFreshSensorReadingsForPlot: jest.fn().mockResolvedValue([]),
      upsertSensorPlotReading: jest.fn().mockResolvedValue(undefined),
      logControlDecision: jest.fn().mockResolvedValue(9001),
      updateDecisionLogResult: jest.fn().mockResolvedValue(undefined),
      updateValveState: jest.fn().mockResolvedValue(true),
      getPlotConfiguration: jest.fn().mockResolvedValue({ controlMode: 'MOISTURE' })
    };
  }

  test('handles three moisture notifications and issues expected commands', async () => {
    const repo = makeRepo();

    const valveCommandService = {
      valveMapping: new Map([
        ['SF-U5', 'SV-U5'],
        ['SF-L2', 'SV-L2'],
        ['SF-L3', 'SV-L3']
      ]),
      sendValveCommandWithRetry: jest.fn().mockResolvedValue({})
    };

    const rcs = new RealtimeControlService(repo, valveCommandService, logger, { readingsRepository: repo });

    // Listener not actually connected; we invoke handleNotification directly and pipe to rcs
    const listener = new SensorUpdateListener({}, { debounceWindow: 0 });
    listener.on('sensor_reading', (evt) => rcs.handleSensorReading(evt));

    const now = new Date();
    const msgs = [
      { sensor_id: '0001-0010', sensor_type: 'moisture', value: 45, timestamp: now.toISOString() },
      { sensor_id: '0001-0002', sensor_type: 'moisture', value: 20, timestamp: new Date(now.getTime() + 1000).toISOString() },
      { sensor_id: '0001-0004', sensor_type: 'moisture', value: 55, timestamp: new Date(now.getTime() + 2000).toISOString() }
    ];

    for (const payload of msgs) {
      listener.handleNotification({ channel: 'sensor_evaluation_needed', payload: JSON.stringify(payload) });
    }

    // allow async handlers to complete
    await new Promise((r) => setTimeout(r, 10));

    // Assertions similar to outbox-based e2e
    expect(repo.getSensorPlotMapping).toHaveBeenCalledWith(repo.pool, '00000010');
    expect(repo.getSensorPlotMapping).toHaveBeenCalledWith(repo.pool, '00000002');
    expect(repo.getSensorPlotMapping).toHaveBeenCalledWith(repo.pool, '00000004');

    const calls = valveCommandService.sendValveCommandWithRetry.mock.calls.map((a) => ({ plotId: a[0], level: a[1] }));
    expect(calls).toEqual(expect.arrayContaining([{ plotId: 'SF-U5', level: 1 }, { plotId: 'SF-L2', level: 1 }]));
    expect(calls.find((c) => c.plotId === 'SF-L3')).toBeUndefined();
  });
});