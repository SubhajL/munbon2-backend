const { ValveCommandService } = require('../valveCommandService');

describe('ValveCommandService', () => {
  test('throws when MSSQL pool is unavailable', async () => {
    const svc = new ValveCommandService({
      mssqlPool: null,
      timescaleRepository: { updateValveStatus: jest.fn() },
      valveMapping: new Map([['P1', 'SV_P1']]),
      tableName: 'tb_valve_command_v2_test',
      timezone: 'Asia/Bangkok'
    });

    await expect(
      svc.sendValveCommand('P1', 1, new Date(), 'test')
    ).rejects.toThrow(/MSSQL unavailable/);
  });
});

describe('sendValveCommand', () => {
  test('inserts local time not UTC to MSSQL', async () => {
    const mockRequest = {
      input: jest.fn().mockReturnThis(),
      query: jest.fn().mockResolvedValue({})
    };
    const mockPool = {
      request: jest.fn().mockReturnValue(mockRequest)
    };
    const mockRepo = {
      updateValveStatus: jest.fn().mockResolvedValue(undefined)
    };

    const svc = new ValveCommandService({
      mssqlPool: mockPool,
      timescaleRepository: mockRepo,
      valveMapping: new Map([['P1', 'SV-U1']]),
      tableName: 'tb_valve_command_v2_test',
      timezone: 'Asia/Bangkok'
    });

    const utcTime = new Date('2024-01-15T17:30:00Z');
    await svc.sendValveCommand('P1', 1, utcTime, 'test');

    expect(mockRequest.input).toHaveBeenCalledWith(
      'startdatetime',
      expect.any(Object),
      '2024-01-16 00:30:00'
    );
  });

  test('UTC 2024-01-15T17:30:00Z becomes 2024-01-16 00:30:00 local', async () => {
    const mockRequest = {
      input: jest.fn().mockReturnThis(),
      query: jest.fn().mockResolvedValue({})
    };
    const mockPool = {
      request: jest.fn().mockReturnValue(mockRequest)
    };
    const mockRepo = {
      updateValveStatus: jest.fn().mockResolvedValue(undefined)
    };

    const svc = new ValveCommandService({
      mssqlPool: mockPool,
      timescaleRepository: mockRepo,
      valveMapping: new Map([['P1', 'SV-U1']]),
      tableName: 'tb_valve_command_v2_test',
      timezone: 'Asia/Bangkok'
    });

    const utc = new Date('2024-01-15T17:30:00Z');
    await svc.sendValveCommand('P1', 1, utc, 'test');

    const dateTimeCall = mockRequest.input.mock.calls.find(
      (call) => call[0] === 'startdatetime'
    );
    expect(dateTimeCall[2]).toBe('2024-01-16 00:30:00');
  });

  test('local time matches configured timezone offset', async () => {
    const mockRequest = {
      input: jest.fn().mockReturnThis(),
      query: jest.fn().mockResolvedValue({})
    };
    const mockPool = {
      request: jest.fn().mockReturnValue(mockRequest)
    };
    const mockRepo = {
      updateValveStatus: jest.fn().mockResolvedValue(undefined)
    };

    const svc = new ValveCommandService({
      mssqlPool: mockPool,
      timescaleRepository: mockRepo,
      valveMapping: new Map([['P1', 'SV-U1']]),
      tableName: 'tb_valve_command_v2_test',
      timezone: 'Asia/Bangkok'
    });

    const utcMidnight = new Date('2024-01-15T00:00:00Z');
    await svc.sendValveCommand('P1', 1, utcMidnight, 'test');

    const dateTimeCall = mockRequest.input.mock.calls.find(
      (call) => call[0] === 'startdatetime'
    );
    expect(dateTimeCall[2]).toBe('2024-01-15 07:00:00');
  });
});
