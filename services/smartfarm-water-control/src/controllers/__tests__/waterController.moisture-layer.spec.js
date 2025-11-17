const { WaterController } = require('../waterController');

describe('WaterController uses moisture layer from thresholds', () => {
  test('passes thresholds.moistureLayer to sensorData.getSensorReading', async () => {
    const mockServices = {
      controlMode: { getMode: jest.fn(() => 'MOISTURE') },
      moistureControl: { evaluateMoistureStatus: jest.fn(() => ({ action: 'MAINTAIN', reason: 'ok' })) },
      awdControl: {},
      valveCommand: { getValveStatus: jest.fn(async () => ({ status: 'OFF' })) },
      valveAudit: null,
      waterPlanning: {},
      waterBalance: { startIrrigation: jest.fn(), stopIrrigation: jest.fn() },
      sensorData: { getSensorReading: jest.fn(async () => ({ value: 30 })) },
      timescaleRepository: {
        getControlThresholds: jest.fn(async () => ({ moistureLowerThreshold: 10, moistureUpperThreshold: 20, moistureLayer: 'deep' }))
      },
      config: { plots: [] }
    };

    const wc = new WaterController(mockServices);

    await wc.processPlot({ plotId: 'P001', sensorId: 'MS-0001', valveName: 'VALVE1' });

    expect(mockServices.sensorData.getSensorReading).toHaveBeenCalledWith('MS-0001', { moistureLayer: 'deep' });
  });
});