const logger = require('../utils/logger');

class ControlModeService {
  constructor(timescaleRepository, cacheTtlMs = 300000) {
    this.repository = timescaleRepository;
    this.cacheTtlMs = cacheTtlMs;
    this.cache = new Map();
    this.lastLoadTime = null;
  }

  async loadModes() {
    try {
      const modes = await this.repository.getControlModes();
      this.cache.clear();
      modes.forEach((mode) => {
        this.cache.set(mode.plotId, mode.controlMode);
      });
      this.lastLoadTime = Date.now();
      logger.info({ count: modes.length }, 'Loaded control modes into cache');
    } catch (error) {
      logger.error({ error }, 'Failed to load control modes');
      throw error;
    }
  }

  getMode(plotId) {
    if (this.lastLoadTime === null) {
      throw new Error('Control modes not loaded. Call loadModes() first.');
    }

    if (!this.cache.has(plotId)) {
      throw new Error(`No control mode configured for plot: ${plotId}`);
    }

    return this.cache.get(plotId);
  }

  isCacheStale() {
    if (this.lastLoadTime === null) {
      return true;
    }

    const age = Date.now() - this.lastLoadTime;
    return age > this.cacheTtlMs;
  }

  async refreshIfStale() {
    if (this.isCacheStale()) {
      logger.info('Cache is stale, refreshing control modes');
      await this.loadModes();
    }
  }

  getAllModes() {
    return Object.fromEntries(this.cache);
  }

  getLastLoadTime() {
    return this.lastLoadTime;
  }
}

module.exports = { ControlModeService };
