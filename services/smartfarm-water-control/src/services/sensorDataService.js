const logger = require('../utils/logger');

class SensorDataService {
  constructor(config) {
    this.timescaleRepository = config.timescaleRepository;
    this.cache = new Map();
    this.cacheTimeout = 60000; // 1 minute cache
  }

  async getSensorReading(sensorId) {
    try {
      // Check cache first
      const cached = this.cache.get(sensorId);
      if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
        return cached.data;
      }

      // Determine sensor type from ID
      const sensorType = this.determineSensorType(sensorId);

      // Get reading from database
      const reading = await this.timescaleRepository.getLatestSensorReading(
        sensorId,
        sensorType
      );

      if (!reading) {
        logger.warn({ sensorId }, 'No data found for sensor');
        return null;
      }

      // Format reading
      const formattedReading = {
        sensorId: reading.sensorId,
        timestamp: new Date(reading.timestamp),
        type: reading.type,
        value: reading.value,
        unit: reading.unit,
        depth: sensorType === 'moisture' ? 30 : undefined // Default 30cm depth for moisture
      };

      // Cache the result
      this.cache.set(sensorId, {
        data: formattedReading,
        timestamp: Date.now()
      });

      return formattedReading;
    } catch (error) {
      logger.error({ error, sensorId }, 'Failed to get sensor reading');

      // Return last cached value if available
      const cached = this.cache.get(sensorId);
      if (cached) {
        logger.warn({ sensorId }, 'Returning stale cached data due to error');
        return cached.data;
      }

      return null;
    }
  }

  determineSensorType(sensorId) {
    if (sensorId.includes('AWD') || sensorId.includes('WL')) {
      return 'water-level';
    } else if (sensorId.includes('MOIST') || sensorId.includes('MS')) {
      return 'moisture';
    }
    throw new Error(`Unknown sensor type for ID: ${sensorId}`);
  }

  async getSensorHistory(sensorId, startDate, endDate) {
    try {
      const sensorType = this.determineSensorType(sensorId);

      const history = await this.timescaleRepository.getSensorHistory(
        sensorId,
        sensorType,
        startDate,
        endDate
      );

      return history.map((reading) => ({
        sensorId: reading.sensorId,
        timestamp: new Date(reading.timestamp),
        type: reading.type,
        value: reading.value,
        unit: reading.unit,
        depth: sensorType === 'moisture' ? 30 : undefined
      }));
    } catch (error) {
      logger.error({ error, sensorId }, 'Failed to get sensor history');
      return [];
    }
  }

  async checkSensorHealth(sensorId) {
    try {
      const sensorType = this.determineSensorType(sensorId);
      return await this.timescaleRepository.checkSensorHealth(
        sensorId,
        sensorType
      );
    } catch (error) {
      return {
        sensorId,
        healthy: false,
        reason: error.message
      };
    }
  }

  clearCache() {
    this.cache.clear();
  }
}

module.exports = { SensorDataService };