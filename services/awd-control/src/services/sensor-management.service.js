"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.sensorManagementService = exports.SensorManagementService = void 0;
const sensor_repository_1 = require("../repositories/sensor.repository");
const redis_1 = require("../config/redis");
const logger_1 = require("../utils/logger");
const redis_2 = require("../config/redis");
class SensorManagementService {
    redis = (0, redis_1.getRedisClient)();
    CACHE_TTL = 300;
    MOISTURE_THRESHOLD_DRY = 30;
    DEFAULT_DRYING_DAYS = 7;
    async getCurrentWaterLevel(fieldId) {
        try {
            const cacheKey = redis_2.RedisKeys.sensorReading(`water_${fieldId}`);
            const cached = await this.redis.get(cacheKey);
            if (cached) {
                return JSON.parse(cached);
            }
            await sensor_repository_1.sensorRepository.getFieldSensorConfig(fieldId);
            const waterLevel = await sensor_repository_1.sensorRepository.getLatestWaterLevel(fieldId);
            if (waterLevel) {
                await this.redis.setex(cacheKey, this.CACHE_TTL, JSON.stringify(waterLevel));
                if (waterLevel.source === 'sensor') {
                    await sensor_repository_1.sensorRepository.updateSensorLastReading(waterLevel.sensorId, waterLevel.time);
                }
                logger_1.logger.info({
                    fieldId,
                    waterLevel: waterLevel.waterLevelCm,
                    source: waterLevel.source
                }, 'Water level reading retrieved');
            }
            else {
                logger_1.logger.warn({ fieldId }, 'No water level data available');
            }
            return waterLevel;
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId }, 'Failed to get current water level');
            throw error;
        }
    }
    async getCurrentMoistureLevel(fieldId) {
        try {
            const cacheKey = redis_2.RedisKeys.sensorReading(`moisture_${fieldId}`);
            const cached = await this.redis.get(cacheKey);
            if (cached) {
                return JSON.parse(cached);
            }
            const moisture = await sensor_repository_1.sensorRepository.getLatestMoistureReading(fieldId);
            if (moisture) {
                await this.redis.setex(cacheKey, this.CACHE_TTL, JSON.stringify(moisture));
                await sensor_repository_1.sensorRepository.updateSensorLastReading(moisture.sensorId, moisture.time);
                logger_1.logger.info({
                    fieldId,
                    moisturePercent: moisture.moisturePercent,
                    depth: moisture.depth
                }, 'Moisture reading retrieved');
            }
            return moisture;
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId }, 'Failed to get current moisture level');
            throw error;
        }
    }
    async checkIrrigationNeed(fieldId) {
        try {
            const sensorConfig = await sensor_repository_1.sensorRepository.getFieldSensorConfig(fieldId);
            const waterLevel = await this.getCurrentWaterLevel(fieldId);
            if (waterLevel) {
                const thresholds = await this.getAWDThresholds(fieldId);
                if (waterLevel.waterLevelCm <= -thresholds.dryingDepth) {
                    return {
                        needsIrrigation: true,
                        reason: 'water_level_threshold',
                        data: {
                            currentLevel: waterLevel.waterLevelCm,
                            threshold: -thresholds.dryingDepth,
                            source: waterLevel.source
                        }
                    };
                }
            }
            if (sensorConfig.hasMoistureSensor) {
                const moisture = await this.getCurrentMoistureLevel(fieldId);
                if (moisture && moisture.moisturePercent < this.MOISTURE_THRESHOLD_DRY) {
                    return {
                        needsIrrigation: true,
                        reason: 'moisture_threshold',
                        data: {
                            currentMoisture: moisture.moisturePercent,
                            threshold: this.MOISTURE_THRESHOLD_DRY
                        }
                    };
                }
            }
            if (!sensorConfig.hasWaterLevelSensor && !sensorConfig.hasMoistureSensor) {
                const daysSinceDrying = await this.getDaysSinceDryingStart(fieldId);
                if (daysSinceDrying >= (sensorConfig.dryingDayCount || this.DEFAULT_DRYING_DAYS)) {
                    return {
                        needsIrrigation: true,
                        reason: 'drying_days_exceeded',
                        data: {
                            daysSinceDrying,
                            threshold: sensorConfig.dryingDayCount || this.DEFAULT_DRYING_DAYS
                        }
                    };
                }
            }
            return {
                needsIrrigation: false,
                reason: 'within_thresholds',
                data: {
                    waterLevel: waterLevel?.waterLevelCm,
                    moisture: sensorConfig.hasMoistureSensor ?
                        (await this.getCurrentMoistureLevel(fieldId))?.moisturePercent : null
                }
            };
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId }, 'Failed to check irrigation need');
            throw error;
        }
    }
    async getAWDThresholds(_fieldId) {
        return {
            dryingDepth: parseInt(process.env.DEFAULT_DRYING_DEPTH || '15'),
            safeAwdDepth: parseInt(process.env.SAFE_AWD_DEPTH || '10'),
            emergencyThreshold: parseInt(process.env.EMERGENCY_THRESHOLD || '25')
        };
    }
    async getDaysSinceDryingStart(fieldId) {
        try {
            const stateKey = redis_2.RedisKeys.fieldState(fieldId);
            const state = await this.redis.hget(stateKey, 'dryingStartDate');
            if (state) {
                const startDate = new Date(state);
                const now = new Date();
                const diffTime = Math.abs(now.getTime() - startDate.getTime());
                const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
                return diffDays;
            }
            return 0;
        }
        catch (error) {
            logger_1.logger.error({ error, field: fieldId }, 'Failed to get days since drying start');
            return 0;
        }
    }
    async getFieldSensorHealth(fieldId) {
        try {
            const sensorConfig = await sensor_repository_1.sensorRepository.getFieldSensorConfig(fieldId);
            const allSensorIds = [
                ...sensorConfig.waterLevelSensorIds,
                ...sensorConfig.moistureSensorIds
            ];
            const sensorStatuses = [];
            const issues = [];
            let unhealthyCount = 0;
            for (const sensorId of allSensorIds) {
                const status = await sensor_repository_1.sensorRepository.getSensorStatus(sensorId);
                if (status) {
                    sensorStatuses.push(status);
                    if (!status.isActive) {
                        issues.push(`Sensor ${sensorId} is inactive`);
                        unhealthyCount++;
                    }
                    else if (status.reliability < 0.5) {
                        issues.push(`Sensor ${sensorId} has low reliability (${status.reliability})`);
                        unhealthyCount++;
                    }
                    if (status.batteryLevel && status.batteryLevel < 3.0) {
                        issues.push(`Sensor ${sensorId} has low battery (${status.batteryLevel}V)`);
                    }
                }
            }
            let overall;
            if (unhealthyCount === 0) {
                overall = 'healthy';
            }
            else if (unhealthyCount < allSensorIds.length / 2) {
                overall = 'degraded';
            }
            else {
                overall = 'critical';
            }
            return {
                overall,
                sensors: sensorStatuses,
                issues
            };
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId }, 'Failed to get field sensor health');
            throw error;
        }
    }
    async processSensorData(data) {
        try {
            const { sensorId, fieldId, type, value, timestamp } = data;
            if (type === 'water_level') {
                const reading = {
                    time: new Date(timestamp),
                    sensorId,
                    fieldId,
                    waterLevelCm: value,
                    source: 'sensor',
                    ...data.metadata
                };
                const cacheKey = redis_2.RedisKeys.sensorReading(`water_${fieldId}`);
                await this.redis.setex(cacheKey, this.CACHE_TTL, JSON.stringify(reading));
            }
            else if (type === 'moisture') {
                const reading = {
                    time: new Date(timestamp),
                    sensorId,
                    fieldId,
                    moisturePercent: value,
                    depth: data.metadata?.depth || 0,
                    ...data.metadata
                };
                const cacheKey = redis_2.RedisKeys.sensorReading(`moisture_${fieldId}`);
                await this.redis.setex(cacheKey, this.CACHE_TTL, JSON.stringify(reading));
            }
            await sensor_repository_1.sensorRepository.updateSensorLastReading(sensorId, new Date(timestamp));
            const irrigationCheck = await this.checkIrrigationNeed(fieldId);
            if (irrigationCheck.needsIrrigation) {
                logger_1.logger.info({
                    fieldId,
                    reason: irrigationCheck.reason,
                    data: irrigationCheck.data
                }, 'Irrigation needed based on sensor data');
            }
            logger_1.logger.debug({
                sensorId,
                fieldId,
                type,
                value
            }, 'Sensor data processed');
        }
        catch (error) {
            logger_1.logger.error({ error, data }, 'Failed to process sensor data');
            throw error;
        }
    }
}
exports.SensorManagementService = SensorManagementService;
exports.sensorManagementService = new SensorManagementService();
//# sourceMappingURL=sensor-management.service.js.map