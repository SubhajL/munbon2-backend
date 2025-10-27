class OutboxPoller {
  constructor({
    repository,
    realtimeControlService,
    pollIntervalMs = 5000,
    batchSize = 100,
    logger = console,
    pool = null
  }) {
    this.repository = repository;
    this.realtimeControlService = realtimeControlService;
    this.pollIntervalMs = pollIntervalMs;
    this.batchSize = batchSize;
    this.logger = logger;
    this.pool = pool;
    this.pollTimer = null;
    this.isStopped = false;

    // Metrics
    this.processedCount = 0;
    this.errorCount = 0;
    this.lastPollTime = null;
  }

  start() {
    if (this.pollTimer) {
      return;
    }

    this.isStopped = false;

    this.pollTimer = setInterval(async () => {
      if (!this.isStopped) {
        await this.poll();
      }
    }, this.pollIntervalMs);

    this.logger.info(
      { pollIntervalMs: this.pollIntervalMs, batchSize: this.batchSize },
      'Outbox poller started'
    );
  }

  stop() {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }

    this.isStopped = true;

    this.logger.info('Outbox poller stopped');
  }

  async poll() {
    try {
      this.lastPollTime = new Date();

      const entries = await this.repository.fetchUnprocessedOutboxEntries(
        this.pool,
        this.batchSize
      );

      if (entries.length === 0) {
        return;
      }

      this.logger.debug({ count: entries.length }, 'Processing outbox entries');

      for (const entry of entries) {
        try {
          await this.realtimeControlService.handleSensorReading({
            sensorId: entry.sensorId,
            sensorType: entry.sensorType,
            value: entry.value,
            timestamp: entry.timestamp,
            locationLat: entry.locationLat,
            locationLng: entry.locationLng
          });

          await this.repository.markOutboxEntryProcessed(
            this.pool,
            entry.id,
            new Date()
          );

          this.processedCount++;

          this.logger.debug(
            { outboxId: entry.id, sensorId: entry.sensorId },
            'Outbox entry processed successfully'
          );
        } catch (error) {
          this.errorCount++;

          this.logger.error(
            {
              error,
              outboxId: entry.id,
              sensorId: entry.sensorId,
              sensorType: entry.sensorType
            },
            'Failed to process outbox entry'
          );
        }
      }
    } catch (error) {
      this.logger.error({ error }, 'Error during outbox polling');
    }
  }

  getMetrics() {
    return {
      processedCount: this.processedCount,
      errorCount: this.errorCount,
      lastPollTime: this.lastPollTime
    };
  }

  resetMetrics() {
    this.processedCount = 0;
    this.errorCount = 0;
    this.lastPollTime = null;
  }
}

module.exports = OutboxPoller;
