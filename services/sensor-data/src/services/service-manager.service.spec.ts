import {
  getServicesList,
  getServiceStatus,
  startService,
  stopService,
  calculateUptime
} from './service-manager.service';

describe('service-manager', () => {
  describe('calculateUptime', () => {
    test('formats zero uptime', () => {
      const result = calculateUptime(0);
      expect(result).toBe('0d 0h 0m');
    });

    test('formats hours and minutes', () => {
      const oneHourAgo = Date.now() - (60 * 60 * 1000);
      const result = calculateUptime(oneHourAgo);
      expect(result).toBe('0d 1h 0m');
    });

    test('formats days, hours, and minutes', () => {
      const oneDayAndTwoHoursAgo = Date.now() - (26 * 60 * 60 * 1000);
      const result = calculateUptime(oneDayAndTwoHoursAgo);
      expect(result).toBe('1d 2h 0m');
    });
  });

  describe('getServicesList', () => {
    test('returns array of services from PM2', async () => {
      const services = await getServicesList();
      
      expect(Array.isArray(services)).toBe(true);
      
      if (services.length > 0) {
        const service = services[0];
        expect(service).toHaveProperty('name');
        expect(service).toHaveProperty('status');
        expect(service).toHaveProperty('cpu');
        expect(service).toHaveProperty('memory');
        expect(service).toHaveProperty('restartCount');
        expect(service).toHaveProperty('uptimeFormatted');
      }
    });

    test('completes within reasonable timeout', async () => {
      const startTime = Date.now();
      await getServicesList();
      const duration = Date.now() - startTime;
      
      expect(duration).toBeLessThan(5000);
    }, 10000);
  });

  describe('getServiceStatus', () => {
    test('returns service status for existing service', async () => {
      const services = await getServicesList();
      
      if (services.length === 0) {
        console.warn('No PM2 services running, skipping test');
        return;
      }

      const firstService = services[0];
      const status = await getServiceStatus(firstService.name);
      
      expect(status.name).toBe(firstService.name);
      expect(typeof status.status).toBe('string');
      expect(typeof status.cpu).toBe('number');
      expect(typeof status.memory).toBe('number');
    });

    test('throws error for non-existent service', async () => {
      await expect(
        getServiceStatus('non-existent-service-xyz123')
      ).rejects.toThrow('Service not found');
    });
  });

  describe('startService', () => {
    test('starts a stopped service', async () => {
      const services = await getServicesList();
      const stoppedService = services.find(s => s.status === 'stopped');
      
      if (!stoppedService) {
        console.warn('No stopped services found, skipping test');
        return;
      }

      await startService(stoppedService.name);
      
      // Wait a bit for PM2 to update
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      const status = await getServiceStatus(stoppedService.name);
      expect(status.status).toBe('online');
      
      // Clean up - stop it again
      await stopService(stoppedService.name);
    }, 15000);
  });

  describe('stopService', () => {
    test('stops a running service', async () => {
      const services = await getServicesList();
      const runningService = services.find(s => s.status === 'online');
      
      if (!runningService) {
        console.warn('No running services found, skipping test');
        return;
      }

      await stopService(runningService.name);
      
      // Wait a bit for PM2 to update
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      const status = await getServiceStatus(runningService.name);
      expect(status.status).toBe('stopped');
    }, 15000);
  });
});
