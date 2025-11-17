const { describe, test, expect, beforeEach } = require('@jest/globals');
const { WaterController } = require('../../src/controllers/waterController');

function buildController(overrides = {}) {
  const services = {
    controlMode: {
      getMode: jest.fn(),
    },
    moistureControl: {
      evaluateMoistureStatus: jest.fn(),
    },
    awdControl: {
      evaluateAWDStatus: jest.fn(),
      recordIrrigationStart: jest.fn(),
    },
    valveCommand: {
      sendValveCommand: jest.fn(),
      getValveStatus: jest.fn(),
    },
    valveAudit: {
      logValveChange: jest.fn(),
      updateCommandResult: jest.fn(),
    },
    waterBalance: {
      startIrrigation: jest.fn(),
      stopIrrigation: jest.fn(),
    },
    sensorData: {
      getSensorReading: jest.fn(),
    },
    timescaleRepository: {
      pool: {},
      getControlThresholds: jest.fn(),
    },
    config: {
      plots: [
        {
          plotId: 'plot-1',
          sensorId: 'sensor-1',
          valveName: 'SV_001',
        },
      ],
    },
    ...overrides,
  };

  const controller = new WaterController(services);
  return { controller, services };
}

describe('WaterController audit integration', () => {
  let controller;
  let services;

  beforeEach(() => {
    ({ controller, services } = buildController());

    services.controlMode.getMode.mockReturnValue('MOISTURE');
    services.sensorData.getSensorReading.mockResolvedValue({
      sensorId: 'sensor-1',
      value: 35,
      timestamp: new Date('2025-01-01T00:00:00Z'),
    });
    services.timescaleRepository.getControlThresholds.mockResolvedValue({
      moistureLowerThreshold: 40,
      moistureUpperThreshold: 60,
      waterLevelLowerThreshold: null,
      waterLevelUpperThreshold: null,
    });
    services.valveCommand.getValveStatus.mockResolvedValue({
      status: 'OFF',
      valveName: 'SV_001',
    });
    services.moistureControl.evaluateMoistureStatus.mockReturnValue({
      action: 'ON',
      reason: 'Moisture below lower threshold',
    });
    services.valveCommand.sendValveCommand.mockResolvedValue({
      success: true,
    });
    services.valveAudit.logValveChange.mockResolvedValue(42);
    services.valveCommand.tableName = 'tb_valve_command_v2_test';
  });

  test('logs and updates audit when cron loop turns valve on', async () => {
    await controller.processPlot({
      plotId: 'plot-1',
      sensorId: 'sensor-1',
      valveName: 'SV_001',
    });

    expect(services.valveAudit.logValveChange).toHaveBeenCalledWith(
      expect.objectContaining({
        plotId: 'plot-1',
        valveName: 'SV_001',
        triggeredBy: 'SCHEDULED',
        controlMode: 'MOISTURE',
        valveCommandSent: true,
        action: 'TURN_ON',
      }),
    );

    expect(services.valveCommand.sendValveCommand).toHaveBeenCalledWith(
      'plot-1',
      1,
      expect.any(Date),
      'Moisture below lower threshold',
    );

    expect(services.valveAudit.updateCommandResult).toHaveBeenCalledWith(
      42,
      true,
      null,
    );
  });

  test('records audit failure when MSSQL command throws', async () => {
    const error = new Error('MSSQL unavailable');
    services.valveCommand.sendValveCommand.mockRejectedValue(error);

    await expect(
      controller.processPlot({
        plotId: 'plot-1',
        sensorId: 'sensor-1',
        valveName: 'SV_001',
      }),
    ).rejects.toThrow('MSSQL unavailable');

    expect(services.valveAudit.logValveChange).toHaveBeenCalled();
    expect(services.valveAudit.updateCommandResult).toHaveBeenCalledWith(
      42,
      false,
      'MSSQL unavailable',
    );
  });
});
