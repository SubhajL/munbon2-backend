const { RealtimeControlService } = require('../realtimeControlService');

describe('handleSensorReading - averaging behavior', () => {
  let service;
  let mockRepository;
  let mockValveCommandService;
  let mockLogger;

  beforeEach(() => {
    mockLogger = {
      debug: jest.fn(),
      info: jest.fn(),
      warn: jest.fn(),
      error: jest.fn()
    };

    mockRepository = {
      pool: { query: jest.fn() },
      getSensorPlotMapping: jest.fn(),
      getControlThresholds: jest.fn(),
      getValveState: jest.fn(),
      deleteStaleReadingsForSensor: jest.fn(),
      getFreshSensorReadingsForPlot: jest.fn(),
      upsertSensorPlotReading: jest.fn(),
      logControlDecision: jest.fn(),
      updateValveState: jest.fn(),
      updateDecisionLogResult: jest.fn()
    };

    mockValveCommandService = {
      sendValveCommandWithRetry: jest.fn()
    };

    service = new RealtimeControlService(
      mockRepository,
      mockValveCommandService,
      mockLogger,
      {
        readingsRepository: mockRepository
      }
    );
  });

  test('uses raw value when only one sensor has fresh reading', async () => {
    mockRepository.getSensorPlotMapping.mockResolvedValue({
      plotId: 'P001',
      sensorType: 'moisture'
    });

    mockRepository.getControlThresholds.mockResolvedValue({
      moistureLowerThreshold: 30,
      moistureUpperThreshold: 70
    });

    mockRepository.getValveState.mockResolvedValue({
      currentState: 'OFF'
    });

    mockRepository.deleteStaleReadingsForSensor.mockResolvedValue([]);

    // Only one fresh reading
    mockRepository.getFreshSensorReadingsForPlot.mockResolvedValue([
      { sensorId: '00000001', value: 45.0, timestamp: new Date() }
    ]);

    mockRepository.logControlDecision.mockResolvedValue(1);

    await service.handleSensorReading({
      sensorId: '00000001',
      value: 45.0,
      timestamp: new Date(),
      sensorType: 'moisture'
    });

    expect(mockRepository.upsertSensorPlotReading).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        sensorId: '00000001',
        value: 45.0,
        contributingSensorIds: ['00000001']
      })
    );

    expect(mockLogger.info).not.toHaveBeenCalledWith(
      expect.objectContaining({
        contributingSensors: expect.any(Array)
      }),
      'Computed average from multiple sensors'
    );
  });

  test('computes average when two moisture sensors have fresh readings', async () => {
    mockRepository.getSensorPlotMapping.mockResolvedValue({
      plotId: 'P001',
      sensorType: 'moisture'
    });

    mockRepository.getControlThresholds.mockResolvedValue({
      moistureLowerThreshold: 30,
      moistureUpperThreshold: 70
    });

    mockRepository.getValveState.mockResolvedValue({
      currentState: 'OFF'
    });

    mockRepository.deleteStaleReadingsForSensor.mockResolvedValue([]);

    mockRepository.getFreshSensorReadingsForPlot.mockResolvedValue([
      { sensorId: '00000001', value: 40.0, timestamp: new Date() },
      { sensorId: '00000002', value: 50.0, timestamp: new Date() }
    ]);

    mockRepository.logControlDecision.mockResolvedValue(1);

    await service.handleSensorReading({
      sensorId: '00000001',
      value: 40.0,
      timestamp: new Date(),
      sensorType: 'moisture'
    });

    const expectedAverage = (40.0 + 50.0) / 2;

    expect(mockRepository.upsertSensorPlotReading).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        sensorId: 'AVG_2_sensors',
        value: expectedAverage,
        contributingSensorIds: ['00000001', '00000002']
      })
    );

    expect(mockLogger.info).toHaveBeenCalledWith(
      expect.objectContaining({
        contributingSensors: ['00000001', '00000002'],
        individualValues: [40.0, 50.0],
        averageValue: expectedAverage
      }),
      'Computed average from multiple sensors'
    );
  });

  test('computes average when three water level sensors have fresh readings', async () => {
    mockRepository.getSensorPlotMapping.mockResolvedValue({
      plotId: 'P002',
      sensorType: 'water_level'
    });

    mockRepository.getControlThresholds.mockResolvedValue({
      waterLevelLowerThreshold: 15,
      waterLevelUpperThreshold: 35
    });

    mockRepository.getValveState.mockResolvedValue({
      currentState: 'ON'
    });

    mockRepository.deleteStaleReadingsForSensor.mockResolvedValue([]);

    mockRepository.getFreshSensorReadingsForPlot.mockResolvedValue([
      { sensorId: '00000001', value: 20.0, timestamp: new Date() },
      { sensorId: '00000002', value: 25.0, timestamp: new Date() },
      { sensorId: '00000003', value: 30.0, timestamp: new Date() }
    ]);

    mockRepository.logControlDecision.mockResolvedValue(1);

    await service.handleSensorReading({
      sensorId: '00000001',
      value: 20.0,
      timestamp: new Date(),
      sensorType: 'water_level'
    });

    const expectedAverage = (20.0 + 25.0 + 30.0) / 3;

    expect(mockRepository.upsertSensorPlotReading).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        sensorId: 'AVG_3_sensors',
        value: expectedAverage,
        contributingSensorIds: ['00000001', '00000002', '00000003']
      })
    );
  });

  test('uses raw value when getFreshSensorReadingsForPlot returns empty', async () => {
    mockRepository.getSensorPlotMapping.mockResolvedValue({
      plotId: 'P001',
      sensorType: 'moisture'
    });

    mockRepository.getControlThresholds.mockResolvedValue({
      moistureLowerThreshold: 30,
      moistureUpperThreshold: 70
    });

    mockRepository.getValveState.mockResolvedValue({
      currentState: 'OFF'
    });

    mockRepository.deleteStaleReadingsForSensor.mockResolvedValue([]);
    mockRepository.getFreshSensorReadingsForPlot.mockResolvedValue([]);
    mockRepository.logControlDecision.mockResolvedValue(1);

    await service.handleSensorReading({
      sensorId: '00000001',
      value: 45.0,
      timestamp: new Date(),
      sensorType: 'moisture'
    });

    expect(mockRepository.upsertSensorPlotReading).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        sensorId: '00000001',
        value: 45.0,
        contributingSensorIds: ['00000001']
      })
    );
  });

  test('handles averaging with different sensor types correctly', async () => {
    mockRepository.getSensorPlotMapping.mockResolvedValue({
      plotId: 'P001',
      sensorType: 'moisture'
    });

    mockRepository.getControlThresholds.mockResolvedValue({
      moistureLowerThreshold: 30,
      moistureUpperThreshold: 70
    });

    mockRepository.getValveState.mockResolvedValue({
      currentState: 'OFF'
    });

    mockRepository.deleteStaleReadingsForSensor.mockResolvedValue([]);

    mockRepository.getFreshSensorReadingsForPlot.mockResolvedValue([
      { sensorId: '00000001', value: 35.0, timestamp: new Date() },
      { sensorId: '00000002', value: 45.0, timestamp: new Date() }
    ]);

    mockRepository.logControlDecision.mockResolvedValue(1);

    await service.handleSensorReading({
      sensorId: '00000001',
      value: 35.0,
      timestamp: new Date(),
      sensorType: 'moisture'
    });

    expect(mockRepository.upsertSensorPlotReading).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        units: '%'
      })
    );

    // Reset mocks for water level test
    jest.clearAllMocks();

    mockRepository.getSensorPlotMapping.mockResolvedValue({
      plotId: 'P002',
      sensorType: 'water_level'
    });

    mockRepository.getControlThresholds.mockResolvedValue({
      waterLevelLowerThreshold: 15,
      waterLevelUpperThreshold: 35
    });

    mockRepository.getValveState.mockResolvedValue({
      currentState: 'ON'
    });

    mockRepository.deleteStaleReadingsForSensor.mockResolvedValue([]);

    mockRepository.getFreshSensorReadingsForPlot.mockResolvedValue([
      { sensorId: '00000003', value: 20.0, timestamp: new Date() },
      { sensorId: '00000004', value: 25.0, timestamp: new Date() }
    ]);

    mockRepository.logControlDecision.mockResolvedValue(1);

    await service.handleSensorReading({
      sensorId: '00000003',
      value: 20.0,
      timestamp: new Date(),
      sensorType: 'water_level'
    });

    expect(mockRepository.upsertSensorPlotReading).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        units: 'cm'
      })
    );
  });

  test('gracefully handles error in getFreshSensorReadingsForPlot', async () => {
    mockRepository.getSensorPlotMapping.mockResolvedValue({
      plotId: 'P001',
      sensorType: 'moisture'
    });

    mockRepository.getControlThresholds.mockResolvedValue({
      moistureLowerThreshold: 30,
      moistureUpperThreshold: 70
    });

    mockRepository.getValveState.mockResolvedValue({
      currentState: 'OFF'
    });

    mockRepository.deleteStaleReadingsForSensor.mockResolvedValue([]);
    mockRepository.getFreshSensorReadingsForPlot.mockRejectedValue(
      new Error('Database error')
    );

    await service.handleSensorReading({
      sensorId: '00000001',
      value: 45.0,
      timestamp: new Date(),
      sensorType: 'moisture'
    });

    expect(mockLogger.warn).toHaveBeenCalledWith(
      expect.objectContaining({
        error: expect.any(Error)
      }),
      'Failed to upsert sensor_plot_readings'
    );

    expect(mockRepository.upsertSensorPlotReading).not.toHaveBeenCalled();
  });
});
