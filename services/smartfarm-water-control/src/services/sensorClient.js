const axios = require("axios");
const logger = require("../utils/logger");

class SensorClient {
  constructor(config) {
    this.serviceUrl = config.serviceUrl;
    this.apiKey = config.apiKey;
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
      const endpoint = this.getEndpointForType(sensorType);

      const response = await axios.get(
        `${this.serviceUrl}${endpoint}/${sensorId}/latest`,
        {
          headers: {
            "X-API-Key": this.apiKey,
            Accept: "application/json",
          },
          timeout: 5000,
        },
      );

      if (!response.data || !response.data.data) {
        logger.warn({ sensorId }, "No data returned from sensor service");
        return null;
      }

      const reading = this.parseReading(response.data.data, sensorType);

      // Cache the result
      this.cache.set(sensorId, {
        data: reading,
        timestamp: Date.now(),
      });

      return reading;
    } catch (error) {
      logger.error({ error, sensorId }, "Failed to get sensor reading");

      // Return last cached value if available
      const cached = this.cache.get(sensorId);
      if (cached) {
        logger.warn({ sensorId }, "Returning stale cached data due to error");
        return cached.data;
      }

      return null;
    }
  }

  determineSensorType(sensorId) {
    if (sensorId.includes("AWD") || sensorId.includes("WL")) {
      return "water-level";
    } else if (sensorId.includes("MOIST") || sensorId.includes("MS")) {
      return "moisture";
    }
    throw new Error(`Unknown sensor type for ID: ${sensorId}`);
  }

  getEndpointForType(sensorType) {
    const endpoints = {
      "water-level": "/api/sensors/water-level",
      moisture: "/api/sensors/moisture",
    };

    return endpoints[sensorType] || "/api/sensors";
  }

  parseReading(data, sensorType) {
    const baseReading = {
      sensorId: data.sensor_id || data.sensorId,
      timestamp: new Date(data.timestamp || data.time),
      unit: data.unit,
    };

    if (sensorType === "water-level") {
      return {
        ...baseReading,
        type: "water-level",
        value: parseFloat(
          data.water_level_cm || data.waterLevelCm || data.value,
        ),
        unit: "cm",
      };
    } else if (sensorType === "moisture") {
      return {
        ...baseReading,
        type: "moisture",
        value: parseFloat(
          data.moisture_percent || data.moisturePercent || data.value,
        ),
        unit: "%",
        depth: data.depth || 30, // Default 30cm depth
      };
    }

    return {
      ...baseReading,
      type: "unknown",
      value: parseFloat(data.value),
    };
  }

  async getSensorHistory(sensorId, startDate, endDate) {
    try {
      const sensorType = this.determineSensorType(sensorId);
      const endpoint = this.getEndpointForType(sensorType);

      const response = await axios.get(
        `${this.serviceUrl}${endpoint}/${sensorId}/history`,
        {
          params: {
            start: startDate.toISOString(),
            end: endDate.toISOString(),
          },
          headers: {
            "X-API-Key": this.apiKey,
            Accept: "application/json",
          },
          timeout: 10000,
        },
      );

      if (!response.data || !response.data.data) {
        return [];
      }

      return response.data.data.map((item) =>
        this.parseReading(item, sensorType),
      );
    } catch (error) {
      logger.error({ error, sensorId }, "Failed to get sensor history");
      return [];
    }
  }

  async checkSensorHealth(sensorId) {
    try {
      const reading = await this.getSensorReading(sensorId);

      if (!reading) {
        return {
          sensorId,
          healthy: false,
          reason: "No data available",
        };
      }

      const age = Date.now() - reading.timestamp.getTime();
      const maxAge = 15 * 60 * 1000; // 15 minutes

      if (age > maxAge) {
        return {
          sensorId,
          healthy: false,
          reason: "Stale data",
          lastReading: reading.timestamp,
        };
      }

      return {
        sensorId,
        healthy: true,
        lastReading: reading.timestamp,
      };
    } catch (error) {
      return {
        sensorId,
        healthy: false,
        reason: error.message,
      };
    }
  }

  clearCache() {
    this.cache.clear();
  }
}

module.exports = { SensorClient };
