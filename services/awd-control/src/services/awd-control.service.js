"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.awdControlService = exports.AWDControlService = void 0;
const redis_1 = require("../config/redis");
const database_1 = require("../config/database");
const logger_1 = require("../utils/logger");
const redis_2 = require("../config/redis");
const sensor_management_service_1 = require("./sensor-management.service");
const kafka_1 = require("../config/kafka");
const weather_integration_1 = require("../integrations/weather.integration");
const awd_control_types_1 = require("../types/awd-control.types");
class AWDControlService {
    redis = (0, redis_1.getRedisClient)();
    postgresPool = (0, database_1.getPostgresPool)();
    CRITICAL_MOISTURE_THRESHOLD = 20;
    RAINFALL_THRESHOLD = 5;
    async initializeFieldControl(fieldId, plantingMethod, startDate) {
        try {
            const schedule = this.getScheduleTemplate(plantingMethod);
            const currentWeek = this.calculateCurrentWeek(startDate);
            const currentPhase = this.getCurrentPhase(schedule, currentWeek);
            const config = {
                fieldId,
                plantingMethod,
                startDate,
                currentWeek,
                currentPhase: currentPhase.phase,
                nextPhaseDate: this.calculateNextPhaseDate(startDate, schedule, currentWeek),
                isActive: true,
                hasRainfallData: false,
                targetWaterLevel: currentPhase.targetWaterLevel
            };
            const configKey = redis_2.RedisKeys.fieldConfig(fieldId);
            await this.redis.hset(configKey, {
                ...config,
                startDate: startDate.toISOString(),
                nextPhaseDate: config.nextPhaseDate.toISOString()
            });
            await this.postgresPool.query(`
        INSERT INTO awd_configurations (
          field_id,
          planting_method,
          start_date,
          current_week,
          current_phase,
          target_water_level,
          active
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (field_id) 
        DO UPDATE SET
          planting_method = $2,
          start_date = $3,
          current_week = $4,
          current_phase = $5,
          target_water_level = $6,
          active = $7,
          updated_at = CURRENT_TIMESTAMP
      `, [
                fieldId,
                plantingMethod,
                startDate,
                currentWeek,
                currentPhase.phase,
                currentPhase.targetWaterLevel,
                true
            ]);
            logger_1.logger.info({
                fieldId,
                plantingMethod,
                startDate,
                currentWeek,
                currentPhase: currentPhase.phase
            }, 'AWD control initialized for field');
            return config;
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId }, 'Failed to initialize AWD control');
            throw error;
        }
    }
    async makeControlDecision(fieldId) {
        try {
            const config = await this.getFieldConfig(fieldId);
            if (!config || !config.isActive) {
                return {
                    fieldId,
                    action: 'maintain',
                    reason: 'Field AWD control not active'
                };
            }
            await this.updateFieldProgress(config);
            const [waterLevel, moistureReading, irrigationCheck] = await Promise.all([
                sensor_management_service_1.sensorManagementService.getCurrentWaterLevel(fieldId),
                sensor_management_service_1.sensorManagementService.getCurrentMoistureLevel(fieldId),
                sensor_management_service_1.sensorManagementService.checkIrrigationNeed(fieldId)
            ]);
            const rainfall = await this.getRainfallData(fieldId);
            const decision = await this.evaluatePhaseRequirements(config, waterLevel?.waterLevelCm || 0, moistureReading?.moisturePercent, rainfall, irrigationCheck);
            logger_1.logger.info({
                fieldId,
                decision: decision.action,
                reason: decision.reason,
                currentPhase: config.currentPhase,
                waterLevel: waterLevel?.waterLevelCm,
                moisture: moistureReading?.moisturePercent
            }, 'AWD control decision made');
            await (0, kafka_1.publishMessage)(kafka_1.KafkaTopics.AWD_CONTROL_COMMANDS, {
                fieldId,
                decision,
                timestamp: new Date().toISOString()
            }, fieldId);
            return decision;
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId }, 'Failed to make control decision');
            throw error;
        }
    }
    async evaluatePhaseRequirements(config, currentWaterLevel, moisturePercent, rainfall, sensorCheck) {
        const notifications = [];
        switch (config.currentPhase) {
            case 'wetting':
                return this.evaluateWettingPhase(config, currentWaterLevel, rainfall, notifications);
            case 'drying':
                return this.evaluateDryingPhase(config, currentWaterLevel, moisturePercent, sensorCheck, notifications);
            case 'preparation':
                return {
                    fieldId: config.fieldId,
                    action: 'start_irrigation',
                    reason: 'Field preparation phase',
                    targetWaterLevel: 10,
                    estimatedDuration: 48,
                    notifications
                };
            case 'harvest':
                return {
                    fieldId: config.fieldId,
                    action: 'stop_irrigation',
                    reason: 'Harvest preparation phase',
                    notifications: [{
                            type: 'phase_change',
                            message: 'Field entering harvest preparation - stop all irrigation',
                            priority: 'high'
                        }]
                };
            default:
                return {
                    fieldId: config.fieldId,
                    action: 'maintain',
                    reason: 'Unknown phase'
                };
        }
    }
    evaluateWettingPhase(config, currentWaterLevel, rainfall, notifications) {
        const schedule = this.getScheduleTemplate(config.plantingMethod);
        const currentPhaseInfo = this.getCurrentPhase(schedule, config.currentWeek);
        if (currentPhaseInfo.requiresFertilizer && config.currentWeek === currentPhaseInfo.week) {
            notifications.push({
                type: 'fertilizer',
                message: `Fertilizer application recommended for ${currentPhaseInfo.description}`,
                priority: 'high',
                scheduledFor: new Date()
            });
        }
        if (rainfall && rainfall.amount > this.RAINFALL_THRESHOLD) {
            const estimatedWaterLevel = currentWaterLevel + (rainfall.amount / 10);
            if (estimatedWaterLevel >= config.targetWaterLevel) {
                return {
                    fieldId: config.fieldId,
                    action: 'stop_irrigation',
                    reason: `Rainfall (${rainfall.amount}mm) sufficient for target level`,
                    notifications
                };
            }
        }
        if (currentWaterLevel >= config.targetWaterLevel) {
            return {
                fieldId: config.fieldId,
                action: 'maintain',
                reason: `Target water level (${config.targetWaterLevel}cm) achieved`,
                notifications
            };
        }
        else {
            return {
                fieldId: config.fieldId,
                action: 'start_irrigation',
                reason: `Water level (${currentWaterLevel}cm) below target (${config.targetWaterLevel}cm)`,
                targetWaterLevel: config.targetWaterLevel,
                estimatedDuration: this.estimateIrrigationDuration(currentWaterLevel, config.targetWaterLevel),
                notifications
            };
        }
    }
    evaluateDryingPhase(config, _currentWaterLevel, moisturePercent, sensorCheck, notifications) {
        if (moisturePercent !== undefined && moisturePercent < this.CRITICAL_MOISTURE_THRESHOLD) {
            notifications.push({
                type: 'emergency',
                message: `Critical moisture level (${moisturePercent}%) - immediate irrigation recommended`,
                priority: 'high'
            });
            return {
                fieldId: config.fieldId,
                action: 'start_irrigation',
                reason: `Moisture critically low (${moisturePercent}%)`,
                targetWaterLevel: 10,
                estimatedDuration: 120,
                notifications
            };
        }
        if (sensorCheck.needsIrrigation && sensorCheck.reason === 'moisture_threshold') {
            return {
                fieldId: config.fieldId,
                action: 'start_irrigation',
                reason: 'Moisture threshold reached',
                targetWaterLevel: 10,
                notifications
            };
        }
        return {
            fieldId: config.fieldId,
            action: 'stop_irrigation',
            reason: `Drying phase - Week ${config.currentWeek}`,
            notifications
        };
    }
    async getFieldConfig(fieldId) {
        try {
            const configKey = redis_2.RedisKeys.fieldConfig(fieldId);
            const cached = await this.redis.hgetall(configKey);
            if (cached && Object.keys(cached).length > 0) {
                return {
                    fieldId: cached.fieldId,
                    plantingMethod: cached.plantingMethod,
                    startDate: new Date(cached.startDate),
                    currentWeek: parseInt(cached.currentWeek),
                    currentPhase: cached.currentPhase,
                    nextPhaseDate: new Date(cached.nextPhaseDate),
                    isActive: cached.isActive === 'true',
                    hasRainfallData: cached.hasRainfallData === 'true',
                    targetWaterLevel: parseInt(cached.targetWaterLevel)
                };
            }
            const result = await this.postgresPool.query(`
        SELECT 
          field_id,
          planting_method,
          start_date,
          current_week,
          current_phase,
          target_water_level,
          active
        FROM awd_configurations
        WHERE field_id = $1
      `, [fieldId]);
            if (result.rows.length === 0) {
                return null;
            }
            const row = result.rows[0];
            const schedule = this.getScheduleTemplate(row.planting_method);
            const config = {
                fieldId: row.field_id,
                plantingMethod: row.planting_method,
                startDate: row.start_date,
                currentWeek: row.current_week,
                currentPhase: row.current_phase,
                nextPhaseDate: this.calculateNextPhaseDate(row.start_date, schedule, row.current_week),
                isActive: row.active,
                hasRainfallData: false,
                targetWaterLevel: row.target_water_level
            };
            await this.redis.hset(configKey, {
                ...config,
                startDate: config.startDate.toISOString(),
                nextPhaseDate: config.nextPhaseDate.toISOString()
            });
            return config;
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId }, 'Failed to get field config');
            return null;
        }
    }
    async updateFieldProgress(config) {
        const currentWeek = this.calculateCurrentWeek(config.startDate);
        if (currentWeek !== config.currentWeek) {
            const schedule = this.getScheduleTemplate(config.plantingMethod);
            const newPhase = this.getCurrentPhase(schedule, currentWeek);
            config.currentWeek = currentWeek;
            config.currentPhase = newPhase.phase;
            config.targetWaterLevel = newPhase.targetWaterLevel;
            config.nextPhaseDate = this.calculateNextPhaseDate(config.startDate, schedule, currentWeek);
            const configKey = redis_2.RedisKeys.fieldConfig(config.fieldId);
            await this.redis.hset(configKey, {
                currentWeek: currentWeek.toString(),
                currentPhase: newPhase.phase,
                targetWaterLevel: newPhase.targetWaterLevel.toString(),
                nextPhaseDate: config.nextPhaseDate.toISOString()
            });
            await this.postgresPool.query(`
        UPDATE awd_configurations
        SET 
          current_week = $2,
          current_phase = $3,
          target_water_level = $4,
          updated_at = CURRENT_TIMESTAMP
        WHERE field_id = $1
      `, [config.fieldId, currentWeek, newPhase.phase, newPhase.targetWaterLevel]);
            await (0, kafka_1.publishMessage)(kafka_1.KafkaTopics.ALERT_NOTIFICATIONS, {
                type: 'phase_change',
                fieldId: config.fieldId,
                message: `Field entering ${newPhase.description} (Week ${currentWeek})`,
                priority: 'medium',
                timestamp: new Date().toISOString()
            }, config.fieldId);
        }
    }
    async getRainfallData(fieldId) {
        try {
            const rainfall = await weather_integration_1.weatherIntegration.getCurrentRainfall(fieldId);
            if (rainfall) {
                const rainfallKey = `awd:rainfall:${fieldId}`;
                await this.redis.setex(rainfallKey, 300, JSON.stringify(rainfall));
            }
            return rainfall;
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId }, 'Failed to get rainfall data');
            return null;
        }
    }
    calculateCurrentWeek(startDate) {
        const now = new Date();
        const diffTime = Math.abs(now.getTime() - startDate.getTime());
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        return Math.floor(diffDays / 7);
    }
    getCurrentPhase(schedule, currentWeek) {
        for (let i = schedule.phases.length - 1; i >= 0; i--) {
            if (currentWeek >= schedule.phases[i].week) {
                return schedule.phases[i];
            }
        }
        return schedule.phases[0];
    }
    calculateNextPhaseDate(startDate, schedule, currentWeek) {
        const currentPhaseIndex = schedule.phases.findIndex(phase => currentWeek >= phase.week &&
            (schedule.phases[schedule.phases.indexOf(phase) + 1]?.week > currentWeek ||
                schedule.phases.indexOf(phase) === schedule.phases.length - 1));
        if (currentPhaseIndex < schedule.phases.length - 1) {
            const nextPhase = schedule.phases[currentPhaseIndex + 1];
            const nextPhaseDate = new Date(startDate);
            nextPhaseDate.setDate(nextPhaseDate.getDate() + (nextPhase.week * 7));
            return nextPhaseDate;
        }
        const endDate = new Date(startDate);
        endDate.setDate(endDate.getDate() + (schedule.totalWeeks * 7));
        return endDate;
    }
    getScheduleTemplate(plantingMethod) {
        return plantingMethod === 'transplanted'
            ? awd_control_types_1.TRANSPLANTED_SCHEDULE
            : awd_control_types_1.DIRECT_SEEDED_SCHEDULE;
    }
    estimateIrrigationDuration(currentLevel, targetLevel) {
        const depthNeeded = targetLevel - currentLevel;
        return Math.max(60, depthNeeded * 60);
    }
    async getPlantingMethodFromGIS(fieldId) {
        try {
            const result = await this.postgresPool.query(`
        SELECT planting_method
        FROM gis.field_attributes
        WHERE field_id = $1
      `, [fieldId]);
            if (result.rows.length > 0 && result.rows[0].planting_method) {
                return result.rows[0].planting_method === 'transplanted'
                    ? 'transplanted'
                    : 'direct-seeded';
            }
            return 'direct-seeded';
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId }, 'Failed to get planting method from GIS');
            return 'direct-seeded';
        }
    }
}
exports.AWDControlService = AWDControlService;
exports.awdControlService = new AWDControlService();
//# sourceMappingURL=awd-control.service.js.map