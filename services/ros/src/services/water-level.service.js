"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.waterLevelService = exports.WaterLevelService = void 0;
const database_1 = require("@config/database");
const logger_1 = require("@utils/logger");
class WaterLevelService {
    /**
     * Get current water level for an area
     */
    async getCurrentWaterLevel(areaId) {
        try {
            const query = `
        SELECT 
          area_id,
          measurement_date,
          measurement_time,
          water_level_m,
          reference_level,
          source,
          sensor_id
        FROM ros.water_level_data
        WHERE area_id = $1
        ORDER BY measurement_date DESC, measurement_time DESC
        LIMIT 1
      `;
            const result = await database_1.pool.query(query, [areaId]);
            if (result.rows.length === 0) {
                return null;
            }
            const row = result.rows[0];
            return {
                areaId: row.area_id,
                measurementDate: row.measurement_date,
                measurementTime: row.measurement_time,
                waterLevelM: parseFloat(row.water_level_m),
                referenceLevel: row.reference_level,
                source: row.source,
                sensorId: row.sensor_id,
            };
        }
        catch (error) {
            logger_1.logger.error('Failed to get current water level', error);
            throw error;
        }
    }
    /**
     * Save water level measurement
     */
    async saveWaterLevel(data) {
        try {
            const query = `
        INSERT INTO ros.water_level_data (
          area_id, 
          measurement_date, 
          measurement_time,
          water_level_m, 
          reference_level, 
          source, 
          sensor_id
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
      `;
            await database_1.pool.query(query, [
                data.areaId,
                data.measurementDate,
                data.measurementTime || null,
                data.waterLevelM,
                data.referenceLevel || 'local_datum',
                data.source,
                data.sensorId || null,
            ]);
            logger_1.logger.info('Water level data saved', {
                areaId: data.areaId,
                level: data.waterLevelM,
                date: data.measurementDate
            });
        }
        catch (error) {
            logger_1.logger.error('Failed to save water level data', error);
            throw error;
        }
    }
    /**
     * Get water level history for an area
     */
    async getWaterLevelHistory(areaId, startDate, endDate) {
        try {
            const query = `
        SELECT 
          area_id,
          measurement_date,
          measurement_time,
          water_level_m,
          reference_level,
          source,
          sensor_id
        FROM ros.water_level_data
        WHERE area_id = $1 
          AND measurement_date BETWEEN $2 AND $3
        ORDER BY measurement_date DESC, measurement_time DESC
      `;
            const result = await database_1.pool.query(query, [areaId, startDate, endDate]);
            return result.rows.map(row => ({
                areaId: row.area_id,
                measurementDate: row.measurement_date,
                measurementTime: row.measurement_time,
                waterLevelM: parseFloat(row.water_level_m),
                referenceLevel: row.reference_level,
                source: row.source,
                sensorId: row.sensor_id,
            }));
        }
        catch (error) {
            logger_1.logger.error('Failed to get water level history', error);
            throw error;
        }
    }
    /**
     * Get average water level for a period
     */
    async getAverageWaterLevel(areaId, startDate, endDate) {
        try {
            const query = `
        SELECT AVG(water_level_m) as avg_level
        FROM ros.water_level_data
        WHERE area_id = $1 
          AND measurement_date BETWEEN $2 AND $3
      `;
            const result = await database_1.pool.query(query, [areaId, startDate, endDate]);
            return result.rows[0]?.avg_level || 0;
        }
        catch (error) {
            logger_1.logger.error('Failed to get average water level', error);
            throw error;
        }
    }
    /**
     * Check if water level is critical (below threshold)
     */
    async checkCriticalLevel(areaId, criticalThreshold) {
        try {
            const currentLevel = await this.getCurrentWaterLevel(areaId);
            if (!currentLevel) {
                return {
                    isCritical: false,
                    currentLevel: null,
                    thresholdDifference: null,
                };
            }
            const isCritical = currentLevel.waterLevelM < criticalThreshold;
            const thresholdDifference = currentLevel.waterLevelM - criticalThreshold;
            return {
                isCritical,
                currentLevel: currentLevel.waterLevelM,
                thresholdDifference,
            };
        }
        catch (error) {
            logger_1.logger.error('Failed to check critical water level', error);
            throw error;
        }
    }
    /**
     * Import water level data from sensors/SCADA
     */
    async importSensorData(data) {
        try {
            for (const record of data) {
                await this.saveWaterLevel({
                    areaId: record.areaId,
                    measurementDate: record.timestamp,
                    measurementTime: record.timestamp.toTimeString().split(' ')[0],
                    waterLevelM: record.waterLevel,
                    source: 'sensor',
                    sensorId: record.sensorId,
                });
            }
            logger_1.logger.info(`Imported ${data.length} water level records from sensors`);
        }
        catch (error) {
            logger_1.logger.error('Failed to import sensor data', error);
            throw error;
        }
    }
    /**
     * Get water level statistics
     */
    async getWaterLevelStatistics(areaId, startDate, endDate) {
        try {
            const query = `
        SELECT 
          MIN(water_level_m) as min_level,
          MAX(water_level_m) as max_level,
          AVG(water_level_m) as avg_level,
          STDDEV(water_level_m) as std_dev,
          COUNT(*) as count
        FROM ros.water_level_data
        WHERE area_id = $1 
          AND measurement_date BETWEEN $2 AND $3
      `;
            const result = await database_1.pool.query(query, [areaId, startDate, endDate]);
            const row = result.rows[0];
            return {
                minLevel: parseFloat(row.min_level) || 0,
                maxLevel: parseFloat(row.max_level) || 0,
                avgLevel: parseFloat(row.avg_level) || 0,
                stdDev: parseFloat(row.std_dev) || 0,
                measurementCount: parseInt(row.count) || 0,
            };
        }
        catch (error) {
            logger_1.logger.error('Failed to get water level statistics', error);
            throw error;
        }
    }
}
exports.WaterLevelService = WaterLevelService;
exports.waterLevelService = new WaterLevelService();
//# sourceMappingURL=water-level.service.js.map