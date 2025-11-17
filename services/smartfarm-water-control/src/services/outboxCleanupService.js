class OutboxCleanupService {
  constructor({
    repository,
    retentionDays = 7,
    cleanupIntervalHours = 24,
    logger = console,
    pool = null
  }) {
    this.repository = repository;
    this.retentionDays = retentionDays;
    this.cleanupIntervalHours = cleanupIntervalHours;
    this.logger = logger;
    this.pool = pool;
    this.cleanupTimer = null;
    this.isStopped = false;
  }

  start() {
    if (this.cleanupTimer) {
      return;
    }

    this.isStopped = false;

    const intervalMs = this.cleanupIntervalHours * 60 * 60 * 1000;

    this.cleanupTimer = setInterval(async () => {
      if (!this.isStopped) {
        await this.cleanup();
      }
    }, intervalMs);

    this.logger.info(
      {
        retentionDays: this.retentionDays,
        cleanupIntervalHours: this.cleanupIntervalHours
      },
      'Outbox cleanup service started'
    );
  }

  stop() {
    if (this.cleanupTimer) {
      clearInterval(this.cleanupTimer);
      this.cleanupTimer = null;
    }

    this.isStopped = true;

    this.logger.info('Outbox cleanup service stopped');
  }

  async cleanup() {
    try {
      const cutoffDate = new Date(
        Date.now() - this.retentionDays * 24 * 60 * 60 * 1000
      );

      const deletedCount = await this.repository.deleteProcessedOutboxEntries(
        this.pool,
        cutoffDate
      );

      this.logger.info(
        { deletedCount, retentionDays: this.retentionDays },
        'Outbox cleanup completed'
      );
    } catch (error) {
      this.logger.error(
        { error, retentionDays: this.retentionDays },
        'Outbox cleanup failed'
      );
    }
  }
}

module.exports = OutboxCleanupService;
