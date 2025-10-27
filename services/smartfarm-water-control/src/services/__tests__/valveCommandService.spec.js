const { ValveCommandService } = require('../valveCommandService');

describe('ValveCommandService', () => {
  test('throws when MSSQL pool is unavailable', async () => {
    const svc = new ValveCommandService({
      mssqlPool: null,
      timescaleRepository: { updateValveStatus: jest.fn() },
      valveMapping: new Map([['P1', 'SV_P1']]),
      tableName: 'tb_valve_command_v2_test'
    });

    await expect(svc.sendValveCommand('P1', 1, new Date(), 'test'))
      .rejects.toThrow(/MSSQL unavailable/);
  });
});