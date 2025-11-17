const {
  describe,
  test,
  expect,
  beforeEach,
  afterEach
} = require('@jest/globals');

describe('OutboxCleanupService', () => {
  let OutboxCleanupService;
  let service;
  let mockRepository;
  let mockLogger;

  beforeEach(() => {
    jest.clearAllTimers();
    jest.useFakeTimers();

    jest.resetModules();
    OutboxCleanupService = require('../outboxCleanupService');

    mockRepository = {
      deleteProcessedOutboxEntries: jest.fn()
    };

    mockLogger = {
      info: jest.fn(),
      warn: jest.fn(),
      error: jest.fn(),
      debug: jest.fn()
    };

    service = new OutboxCleanupService({
      repository: mockRepository,
      retentionDays: 7,
      cleanupIntervalHours: 24,
      logger: mockLogger,
      pool: null
    });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('constructor', () => {
    test('initializes with provided configuration', () => {
      expect(service.repository).toBe(mockRepository);
      expect(service.retentionDays).toBe(7);
      expect(service.cleanupIntervalHours).toBe(24);
      expect(service.pool).toBe(null);
    });

    test('uses default retention and interval', () => {
      const defaultService = new OutboxCleanupService({
        repository: mockRepository,
        logger: mockLogger
      });

      expect(defaultService.retentionDays).toBe(7);
      expect(defaultService.cleanupIntervalHours).toBe(24);
    });
  });

  describe('start', () => {
    test('begins cleanup at configured interval', () => {
      const cleanupSpy = jest
        .spyOn(service, 'cleanup')
        .mockImplementation(() => Promise.resolve());

      service.start();

      expect(cleanupSpy).not.toHaveBeenCalled();

      jest.advanceTimersByTime(24 * 60 * 60 * 1000);

      expect(cleanupSpy).toHaveBeenCalledTimes(1);

      jest.advanceTimersByTime(24 * 60 * 60 * 1000);

      expect(cleanupSpy).toHaveBeenCalledTimes(2);
    });

    test('does not start multiple intervals', () => {
      const cleanupSpy = jest
        .spyOn(service, 'cleanup')
        .mockImplementation(() => Promise.resolve());

      service.start();
      service.start();

      jest.advanceTimersByTime(24 * 60 * 60 * 1000);

      expect(cleanupSpy).toHaveBeenCalledTimes(1);
    });
  });

  describe('stop', () => {
    test('clears cleanup interval', () => {
      const cleanupSpy = jest
        .spyOn(service, 'cleanup')
        .mockImplementation(() => Promise.resolve());

      service.start();
      service.stop();

      jest.advanceTimersByTime(48 * 60 * 60 * 1000);

      expect(cleanupSpy).not.toHaveBeenCalled();
    });

    test('sets isStopped flag', () => {
      service.start();
      service.stop();

      expect(service.isStopped).toBe(true);
    });

    test('handles stop when not started', () => {
      expect(() => service.stop()).not.toThrow();
    });
  });

  describe('cleanup', () => {
    test('deletes processed entries older than retention', async () => {
      const now = new Date('2025-10-23T10:00:00Z');
      jest.setSystemTime(now);

      mockRepository.deleteProcessedOutboxEntries.mockResolvedValue(42);

      await service.cleanup();

      const expectedCutoff = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);

      expect(mockRepository.deleteProcessedOutboxEntries).toHaveBeenCalledWith(
        null,
        expectedCutoff
      );
    });

    test('logs deleted count', async () => {
      mockRepository.deleteProcessedOutboxEntries.mockResolvedValue(42);

      await service.cleanup();

      expect(mockLogger.info).toHaveBeenCalledWith(
        { deletedCount: 42, retentionDays: 7 },
        'Outbox cleanup completed'
      );
    });

    test('handles empty result gracefully', async () => {
      mockRepository.deleteProcessedOutboxEntries.mockResolvedValue(0);

      await expect(service.cleanup()).resolves.not.toThrow();

      expect(mockLogger.info).toHaveBeenCalledWith(
        { deletedCount: 0, retentionDays: 7 },
        'Outbox cleanup completed'
      );
    });

    test('handles errors without crashing', async () => {
      mockRepository.deleteProcessedOutboxEntries.mockRejectedValue(
        new Error('Database error')
      );

      await expect(service.cleanup()).resolves.not.toThrow();

      expect(mockLogger.error).toHaveBeenCalled();
    });

    test('uses correct retention period', async () => {
      const customService = new OutboxCleanupService({
        repository: mockRepository,
        retentionDays: 14,
        logger: mockLogger
      });

      const now = new Date('2025-10-23T10:00:00Z');
      jest.setSystemTime(now);

      mockRepository.deleteProcessedOutboxEntries.mockResolvedValue(0);

      await customService.cleanup();

      const expectedCutoff = new Date(now.getTime() - 14 * 24 * 60 * 60 * 1000);

      expect(mockRepository.deleteProcessedOutboxEntries).toHaveBeenCalledWith(
        null,
        expectedCutoff
      );
    });
  });
});
