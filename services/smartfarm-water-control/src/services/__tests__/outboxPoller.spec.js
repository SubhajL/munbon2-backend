const {
  describe,
  test,
  expect,
  beforeEach,
  afterEach
} = require('@jest/globals');

describe('OutboxPoller', () => {
  let OutboxPoller;
  let poller;
  let mockRepository;
  let mockRealtimeControlService;
  let mockLogger;

  beforeEach(() => {
    jest.clearAllTimers();
    jest.useFakeTimers();

    // Clear module cache to get fresh instance
    jest.resetModules();
    OutboxPoller = require('../outboxPoller');

    mockRepository = {
      fetchUnprocessedOutboxEntries: jest.fn(),
      markOutboxEntryProcessed: jest.fn()
    };

    mockRealtimeControlService = {
      handleSensorReading: jest.fn()
    };

    mockLogger = {
      info: jest.fn(),
      warn: jest.fn(),
      error: jest.fn(),
      debug: jest.fn()
    };

    poller = new OutboxPoller({
      repository: mockRepository,
      realtimeControlService: mockRealtimeControlService,
      pollIntervalMs: 5000,
      batchSize: 100,
      logger: mockLogger
    });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('constructor', () => {
    test('initializes with provided configuration', () => {
      expect(poller.repository).toBe(mockRepository);
      expect(poller.realtimeControlService).toBe(mockRealtimeControlService);
      expect(poller.pollIntervalMs).toBe(5000);
      expect(poller.batchSize).toBe(100);
    });

    test('uses default values when not provided', () => {
      const defaultPoller = new OutboxPoller({
        repository: mockRepository,
        realtimeControlService: mockRealtimeControlService,
        logger: mockLogger
      });

      expect(defaultPoller.pollIntervalMs).toBe(5000);
      expect(defaultPoller.batchSize).toBe(100);
    });
  });

  describe('start', () => {
    test('begins polling at configured interval', () => {
      const pollSpy = jest
        .spyOn(poller, 'poll')
        .mockImplementation(() => Promise.resolve());

      poller.start();

      expect(pollSpy).not.toHaveBeenCalled();

      jest.advanceTimersByTime(5000);

      expect(pollSpy).toHaveBeenCalledTimes(1);

      jest.advanceTimersByTime(5000);

      expect(pollSpy).toHaveBeenCalledTimes(2);
    });

    test('does not start multiple intervals', () => {
      const pollSpy = jest
        .spyOn(poller, 'poll')
        .mockImplementation(() => Promise.resolve());

      poller.start();
      poller.start();

      jest.advanceTimersByTime(5000);

      expect(pollSpy).toHaveBeenCalledTimes(1);
    });
  });

  describe('stop', () => {
    test('clears polling interval', () => {
      const pollSpy = jest
        .spyOn(poller, 'poll')
        .mockImplementation(() => Promise.resolve());

      poller.start();
      poller.stop();

      jest.advanceTimersByTime(10000);

      expect(pollSpy).not.toHaveBeenCalled();
    });

    test('sets isStopped flag', () => {
      poller.start();
      poller.stop();

      expect(poller.isStopped).toBe(true);
    });

    test('handles stop when not started', () => {
      expect(() => poller.stop()).not.toThrow();
    });
  });

  describe('poll', () => {
    test('fetches and processes unprocessed entries', async () => {
      const entries = [
        {
          id: 1,
          sensorId: '00000001',
          sensorType: 'moisture',
          value: 45.5,
          timestamp: new Date('2025-10-23T10:00:00Z')
        },
        {
          id: 2,
          sensorId: '00000002',
          sensorType: 'water_level',
          value: 30.0,
          timestamp: new Date('2025-10-23T10:05:00Z')
        }
      ];

      mockRepository.fetchUnprocessedOutboxEntries.mockResolvedValue(entries);
      mockRealtimeControlService.handleSensorReading.mockResolvedValue();

      await poller.poll();

      expect(mockRepository.fetchUnprocessedOutboxEntries).toHaveBeenCalledWith(
        null,
        100
      );
      expect(
        mockRealtimeControlService.handleSensorReading
      ).toHaveBeenCalledTimes(2);
      expect(
        mockRealtimeControlService.handleSensorReading
      ).toHaveBeenCalledWith({
        sensorId: '00000001',
        sensorType: 'moisture',
        value: 45.5,
        timestamp: entries[0].timestamp
      });
      expect(
        mockRealtimeControlService.handleSensorReading
      ).toHaveBeenCalledWith({
        sensorId: '00000002',
        sensorType: 'water_level',
        value: 30.0,
        timestamp: entries[1].timestamp
      });
    });

    test('marks entries processed after successful handling', async () => {
      const entries = [
        {
          id: 1,
          sensorId: '00000001',
          sensorType: 'moisture',
          value: 45.5,
          timestamp: new Date('2025-10-23T10:00:00Z')
        }
      ];

      mockRepository.fetchUnprocessedOutboxEntries.mockResolvedValue(entries);
      mockRealtimeControlService.handleSensorReading.mockResolvedValue();
      mockRepository.markOutboxEntryProcessed.mockResolvedValue();

      await poller.poll();

      expect(mockRepository.markOutboxEntryProcessed).toHaveBeenCalledWith(
        null,
        1,
        expect.any(Date)
      );
    });

    test('does not mark entries processed on error', async () => {
      const entries = [
        {
          id: 1,
          sensorId: '00000001',
          sensorType: 'moisture',
          value: 45.5,
          timestamp: new Date('2025-10-23T10:00:00Z')
        }
      ];

      mockRepository.fetchUnprocessedOutboxEntries.mockResolvedValue(entries);
      mockRealtimeControlService.handleSensorReading.mockRejectedValue(
        new Error('Processing failed')
      );

      await poller.poll();

      expect(mockRepository.markOutboxEntryProcessed).not.toHaveBeenCalled();
      expect(mockLogger.error).toHaveBeenCalled();
    });

    test('handles empty outbox gracefully', async () => {
      mockRepository.fetchUnprocessedOutboxEntries.mockResolvedValue([]);

      await expect(poller.poll()).resolves.not.toThrow();

      expect(
        mockRealtimeControlService.handleSensorReading
      ).not.toHaveBeenCalled();
      expect(mockRepository.markOutboxEntryProcessed).not.toHaveBeenCalled();
    });

    test('processes entries in order', async () => {
      const entries = [
        {
          id: 1,
          sensorId: '00000001',
          sensorType: 'moisture',
          value: 45.5,
          timestamp: new Date()
        },
        {
          id: 2,
          sensorId: '00000002',
          sensorType: 'moisture',
          value: 50.0,
          timestamp: new Date()
        },
        {
          id: 3,
          sensorId: '00000003',
          sensorType: 'moisture',
          value: 55.0,
          timestamp: new Date()
        }
      ];

      mockRepository.fetchUnprocessedOutboxEntries.mockResolvedValue(entries);
      mockRealtimeControlService.handleSensorReading.mockResolvedValue();

      const callOrder = [];
      mockRealtimeControlService.handleSensorReading.mockImplementation(
        (reading) => {
          callOrder.push(reading.sensorId);
          return Promise.resolve();
        }
      );

      await poller.poll();

      expect(callOrder).toEqual(['00000001', '00000002', '00000003']);
    });

    test('respects batchSize configuration', async () => {
      poller.batchSize = 50;

      mockRepository.fetchUnprocessedOutboxEntries.mockResolvedValue([]);

      await poller.poll();

      expect(mockRepository.fetchUnprocessedOutboxEntries).toHaveBeenCalledWith(
        null,
        50
      );
    });

    test('continues processing remaining entries after one fails', async () => {
      const entries = [
        {
          id: 1,
          sensorId: '00000001',
          sensorType: 'moisture',
          value: 45.5,
          timestamp: new Date()
        },
        {
          id: 2,
          sensorId: '00000002',
          sensorType: 'moisture',
          value: 50.0,
          timestamp: new Date()
        },
        {
          id: 3,
          sensorId: '00000003',
          sensorType: 'moisture',
          value: 55.0,
          timestamp: new Date()
        }
      ];

      mockRepository.fetchUnprocessedOutboxEntries.mockResolvedValue(entries);

      mockRealtimeControlService.handleSensorReading
        .mockResolvedValueOnce()
        .mockRejectedValueOnce(new Error('Failed'))
        .mockResolvedValueOnce();

      await poller.poll();

      expect(
        mockRealtimeControlService.handleSensorReading
      ).toHaveBeenCalledTimes(3);
      expect(mockRepository.markOutboxEntryProcessed).toHaveBeenCalledTimes(2);
      expect(mockRepository.markOutboxEntryProcessed).toHaveBeenCalledWith(
        null,
        1,
        expect.any(Date)
      );
      expect(mockRepository.markOutboxEntryProcessed).toHaveBeenCalledWith(
        null,
        3,
        expect.any(Date)
      );
    });
  });

  describe('metrics', () => {
    test('getMetrics returns current statistics', async () => {
      const metrics = poller.getMetrics();

      expect(metrics).toHaveProperty('processedCount');
      expect(metrics).toHaveProperty('errorCount');
      expect(metrics).toHaveProperty('lastPollTime');
      expect(metrics.processedCount).toBe(0);
      expect(metrics.errorCount).toBe(0);
      expect(metrics.lastPollTime).toBeNull();
    });

    test('metrics increment on successful processing', async () => {
      const entries = [
        {
          id: 1,
          sensorId: '00000001',
          sensorType: 'moisture',
          value: 45.5,
          timestamp: new Date()
        },
        {
          id: 2,
          sensorId: '00000002',
          sensorType: 'moisture',
          value: 50.0,
          timestamp: new Date()
        }
      ];

      mockRepository.fetchUnprocessedOutboxEntries.mockResolvedValue(entries);
      mockRealtimeControlService.handleSensorReading.mockResolvedValue();

      await poller.poll();

      const metrics = poller.getMetrics();
      expect(metrics.processedCount).toBe(2);
      expect(metrics.errorCount).toBe(0);
      expect(metrics.lastPollTime).toBeInstanceOf(Date);
    });

    test('metrics increment on error', async () => {
      const entries = [
        {
          id: 1,
          sensorId: '00000001',
          sensorType: 'moisture',
          value: 45.5,
          timestamp: new Date()
        }
      ];

      mockRepository.fetchUnprocessedOutboxEntries.mockResolvedValue(entries);
      mockRealtimeControlService.handleSensorReading.mockRejectedValue(
        new Error('Processing failed')
      );

      await poller.poll();

      const metrics = poller.getMetrics();
      expect(metrics.processedCount).toBe(0);
      expect(metrics.errorCount).toBe(1);
    });

    test('resetMetrics clears all counters', async () => {
      const entries = [
        {
          id: 1,
          sensorId: '00000001',
          sensorType: 'moisture',
          value: 45.5,
          timestamp: new Date()
        }
      ];

      mockRepository.fetchUnprocessedOutboxEntries.mockResolvedValue(entries);
      mockRealtimeControlService.handleSensorReading.mockResolvedValue();

      await poller.poll();

      expect(poller.getMetrics().processedCount).toBe(1);

      poller.resetMetrics();

      const metrics = poller.getMetrics();
      expect(metrics.processedCount).toBe(0);
      expect(metrics.errorCount).toBe(0);
      expect(metrics.lastPollTime).toBeNull();
    });
  });
});
