const OutboxPoller = require('../outboxPoller');
const { RealtimeControlService } = require('../realtimeControlService');

/**
 * E2E-style test (with mocks) for moisture readings → outbox → control loop → SCADA
 * Scenario:
 *  - Moisture readings arrive for sensors 0001-0010 (45%), 0001-0002 (20%), 0001-0004 (55%)
 *  - OutboxPoller delivers events to RealtimeControlService
 *  - Control thresholds: [50%, 69%]
 *  - Expected actions: TURN_ON for 45% and 20%; MAINTAIN for 55%
 */

describe('E2E moisture → outbox → control → SCADA (mocked DB and SCADA)', () => {
  const logger = { info: jest.fn(), warn: jest.fn(), error: jest.fn(), debug: jest.fn() };

  function makeTimescaleRepo() {
    const mappings = new Map([
      ['00000010', { plotId: 'SF-U5', sensorType: 'moisture' }], // 0001-0010
      ['00000002', { plotId: 'SF-L2', sensorType: 'moisture' }], // 0001-0002
      ['00000004', { plotId: 'SF-L3', sensorType: 'moisture' }] // 0001-0004
    ]);

    const thresholds = {
      moistureLowerThreshold: 50,
      moistureUpperThreshold: 69,
      waterLevelLowerThreshold: -10,
      waterLevelUpperThreshold: 10
    };

    const outbox = [
      {
        id: 1,
        sensorId: '0001-0010',
        sensorType: 'moisture',
        value: 45,
        timestamp: new Date(),
        locationLat: null,
        locationLng: null
      },
      {
        id: 2,
        sensorId: '0001-0002',
        sensorType: 'moisture',
        value: 20,
        timestamp: new Date(Date.now() + 1000),
        locationLat: null,
        locationLng: null
      },
      {
        id: 3,
        sensorId: '0001-0004',
        sensorType: 'moisture',
        value: 55,
        timestamp: new Date(Date.now() + 2000),
        locationLat: null,
        locationLng: null
      }
    ];

    return {
      pool: {},
      // Outbox
      fetchUnprocessedOutboxEntries: jest.fn().mockResolvedValue(outbox),
      markOutboxEntryProcessed: jest.fn().mockResolvedValue(undefined),

      // Mapping / thresholds
      getSensorPlotMapping: jest.fn(async (_db, sensorId) => mappings.get(sensorId)),
      getControlThresholds: jest.fn().mockResolvedValue(thresholds),
      getValveState: jest.fn().mockResolvedValue({ currentState: 'OFF', lastChangedAt: null, lastChangeReason: null }),

      // Reading cache and cleanup
      deleteStaleReadingsForSensor: jest.fn().mockResolvedValue([]),
      getFreshSensorReadingsForPlot: jest.fn().mockResolvedValue([]),
      upsertSensorPlotReading: jest.fn().mockResolvedValue(undefined),

      // Decision logging and updates
      logControlDecision: jest.fn().mockResolvedValue(101),
      updateDecisionLogResult: jest.fn().mockResolvedValue(undefined),
      updateValveState: jest.fn().mockResolvedValue(true),

      // Plot config (for audit path)
      getPlotConfiguration: jest.fn().mockResolvedValue({ controlMode: 'MOISTURE' })
    };
  }

  test('Processes three moisture readings end-to-end and writes SCADA commands when required', async () => {
    const repo = makeTimescaleRepo();

    // SCADA command service (mock)
    const valveCommandService = {
      valveMapping: new Map([
        ['SF-U5', 'SV-U5'],
        ['SF-L2', 'SV-L2'],
        ['SF-L3', 'SV-L3']
      ]),
      sendValveCommandWithRetry: jest.fn().mockResolvedValue({})
    };

    // Optional audit service (mock)
    const valveAuditService = {
      logValveChange: jest.fn().mockResolvedValue(1001),
      updateCommandResult: jest.fn().mockResolvedValue(undefined)
    };

    // Realtime control service under test
    const rcs = new RealtimeControlService(
      repo, // repository for decision log and valve state
      valveCommandService,
      logger,
      { readingsRepository: repo },
      valveAuditService
    );

    const poller = new OutboxPoller({ repository: repo, realtimeControlService: rcs, pollIntervalMs: 999999, batchSize: 100, logger, pool: repo });

    // Act: single poll run processes entire batch
    await poller.poll();

    // Assertions — mapping lookups (normalize: 0001-0010→00000010 etc.)
    expect(repo.getSensorPlotMapping).toHaveBeenCalledWith(repo.pool, '00000010');
    expect(repo.getSensorPlotMapping).toHaveBeenCalledWith(repo.pool, '00000002');
    expect(repo.getSensorPlotMapping).toHaveBeenCalledWith(repo.pool, '00000004');

    // Thresholds fetched per plot
    expect(repo.getControlThresholds).toHaveBeenCalledTimes(3);

    // Upsert sensor_plot_readings 3 times (one per event)
    expect(repo.upsertSensorPlotReading).toHaveBeenCalledTimes(3);

    // Commands: 45% and 20% => TURN_ON (level=1), 55% => MAINTAIN (no command)
    const calls = valveCommandService.sendValveCommandWithRetry.mock.calls.map((args) => ({ plotId: args[0], level: args[1] }));
    expect(calls).toEqual(
      expect.arrayContaining([
        { plotId: 'SF-U5', level: 1 },
        { plotId: 'SF-L2', level: 1 }
      ])
    );
    // Ensure no command for SF-L3 (55%)
    expect(calls.find((c) => c.plotId === 'SF-L3')).toBeUndefined();

    // Valve state updated twice (for two actions)
    expect(repo.updateValveState).toHaveBeenCalledTimes(2);

    // Decision log written for all entries
    expect(repo.logControlDecision).toHaveBeenCalledTimes(3);
    expect(repo.updateDecisionLogResult).toHaveBeenCalledTimes(2); // only when we attempted a command

    // Outbox entries marked processed
    expect(repo.markOutboxEntryProcessed).toHaveBeenCalledTimes(3);

    // Summarize expected mapping/thresholds/commands (documentation inside test for clarity)
    const summary = [
      { sensor: '0001-0010', norm: '00000010', value: 45, plot: 'SF-U5', thresholds: { low: 50, high: 69 }, action: 'TURN_ON', valve: 'SV-U5' },
      { sensor: '0001-0002', norm: '00000002', value: 20, plot: 'SF-L2', thresholds: { low: 50, high: 69 }, action: 'TURN_ON', valve: 'SV-L2' },
      { sensor: '0001-0004', norm: '00000004', value: 55, plot: 'SF-L3', thresholds: { low: 50, high: 69 }, action: 'MAINTAIN', valve: 'SV-L3' }
    ];
    // Keep summary accessible for debugging if test fails
    logger.info(summary, 'E2E moisture summary');
  });
});