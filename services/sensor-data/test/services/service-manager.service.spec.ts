// Converted from Vitest to Jest
// Jest globals (describe/test/expect/jest) are provided by ts-jest
import type { Proc } from 'pm2';

// Mock pm2 module
jest.mock('pm2', () => ({
  default: {
    connect: jest.fn((cb) => cb(null)),
    list: jest.fn(),
    describe: jest.fn(),
    start: jest.fn(),
    stop: jest.fn(),
    disconnect: jest.fn()
  }
}));

import pm2 from 'pm2';
import {
  getServicesList,
  getServiceStatus,
  startService,
  stopService,
  calculateUptime
} from '../../src/services/service-manager.service';

describe.skip('service-manager.service', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('getServicesList', () => {
    test('returns all PM2 managed services', async () => {
      const mockProcesses: any[] = [
        {
          name: 'munbon-scheduler',
          pm2_env: {
            status: 'online',
            pm_uptime: Date.now() - 3600000,
            restart_time: 2,
            created_at: Date.now() - 7200000
          },
          monit: { cpu: 5, memory: 50000000 }
        },
        {
          name: 'munbon-gis',
          pm2_env: {
            status: 'stopped',
            pm_uptime: 0,
            restart_time: 0,
            created_at: Date.now() - 3600000
          },
          monit: { cpu: 0, memory: 0 }
        }
      ];

      jest.mocked(pm2.list as any).mockImplementation((cb: any) => cb(null, mockProcesses as Proc[]));

      const result = await getServicesList();

      expect(result).toHaveLength(2);
      expect(result[0]).toMatchObject({
        name: 'munbon-scheduler',
        status: 'online',
        restartCount: 2
      });
      expect(result[0].uptimeMs).toBeGreaterThan(0);
      expect(result[1].status).toBe('stopped');
    });

    test('throws error when PM2 connection fails', async () => {
      jest.mocked(pm2.list as any).mockImplementation((cb: any) => cb(new Error('Connection failed'), []));

      await expect(getServicesList()).rejects.toThrow('Connection failed');
    });
  });

  describe('getServiceStatus', () => {
    test('returns single service details', async () => {
      const mockProcess: any = {
        name: 'munbon-scheduler',
        pm2_env: {
          status: 'online',
          pm_uptime: Date.now() - 1800000,
          restart_time: 1,
          created_at: Date.now() - 3600000
        },
        monit: { cpu: 3, memory: 45000000 }
      };

      jest.mocked(pm2.describe as any).mockImplementation((name: any, cb: any) => { void name; cb(null, [mockProcess as Proc]); });

      const result = await getServiceStatus('munbon-scheduler');

      expect(result.name).toBe('munbon-scheduler');
      expect(result.status).toBe('online');
      expect(result.uptimeMs).toBeGreaterThan(0);
    });

    test('throws when service not found', async () => {
      jest.mocked(pm2.describe as any).mockImplementation((name: any, cb: any) => { void name; cb(null, []); });

      await expect(getServiceStatus('unknown-service')).rejects.toThrow('Service not found');
    });
  });

  describe('startService', () => {
    test('successfully starts stopped service', async () => {
      jest.mocked(pm2.start as any).mockImplementation((name: any, cb: any) => { void name; cb(null, {} as Proc); });

      await expect(startService('munbon-scheduler')).resolves.toBeUndefined();
      expect(pm2.start).toHaveBeenCalledWith('munbon-scheduler', expect.any(Function));
    });

    test('throws error when start fails', async () => {
      jest.mocked(pm2.start as any).mockImplementation((name: any, cb: any) => { void name; cb(new Error('Start failed'), {} as Proc); });

      await expect(startService('munbon-scheduler')).rejects.toThrow('Start failed');
    });
  });

  describe('stopService', () => {
    test('successfully stops running service', async () => {
      jest.mocked(pm2.stop as any).mockImplementation((name: any, cb: any) => { void name; cb(null, {} as Proc); });

      await expect(stopService('munbon-scheduler')).resolves.toBeUndefined();
      expect(pm2.stop).toHaveBeenCalledWith('munbon-scheduler', expect.any(Function));
    });

    test('throws error when stop fails', async () => {
      jest.mocked(pm2.stop as any).mockImplementation((name: any, cb: any) => { void name; cb(new Error('Stop failed'), {} as Proc); });

      await expect(stopService('munbon-scheduler')).rejects.toThrow('Stop failed');
    });
  });

  describe('calculateUptime', () => {
    test('returns correct formatted string for 2 days', () => {
      const twoDaysAgo = Date.now() - (2 * 24 * 60 * 60 * 1000);
      const result = calculateUptime(twoDaysAgo);

      expect(result).toMatch(/^2d \d+h \d+m$/);
    });

    test('returns correct formatted string for hours and minutes', () => {
      const twoHoursAgo = Date.now() - (2 * 60 * 60 * 1000 + 30 * 60 * 1000);
      const result = calculateUptime(twoHoursAgo);

      expect(result).toMatch(/^0d 2h 3\dm$/);
    });

    test('returns zero when uptime is 0', () => {
      const result = calculateUptime(0);

      expect(result).toBe('0d 0h 0m');
    });
  });
});
