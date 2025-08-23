"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.awdControlServiceV2 = exports.AWDControlServiceV2 = void 0;
const redis_1 = require("../config/redis");
const database_1 = require("../config/database");
const logger_1 = require("../utils/logger");
const redis_2 = require("../config/redis");
const sensor_management_service_1 = require("./sensor-management.service");
const irrigation_controller_service_1 = require("./irrigation-controller.service");
const irrigation_learning_service_1 = require("./irrigation-learning.service");
const kafka_1 = require("../config/kafka");
const weather_integration_1 = require("../integrations/weather.integration");
const awd_control_types_1 = require("../types/awd-control.types");
class AWDControlServiceV2 {
    redis = (0, redis_1.getRedisClient)();
    postgresPool = (0, database_1.getPostgresPool)();
    CRITICAL_MOISTURE_THRESHOLD = 20;
    RAINFALL_THRESHOLD = 5;
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
            const activeIrrigation = await this.getActiveIrrigation(fieldId);
            if (activeIrrigation) {
                return {
                    fieldId,
                    action: 'maintain',
                    reason: `Irrigation already active (${activeIrrigation.status})`,
                    metadata: activeIrrigation
                };
            }
            const decision = await this.evaluatePhaseRequirements(config, waterLevel?.waterLevelCm || 0, moistureReading?.moisturePercent, rainfall, irrigationCheck);
            if (decision.action === 'start_irrigation') {
                const enhancedDecision = await this.enhanceIrrigationDecision(fieldId, decision, waterLevel?.waterLevelCm || 0);
                return enhancedDecision;
            }
            logger_1.logger.info({
                fieldId,
                decision: decision.action,
                reason: decision.reason,
                currentPhase: config.currentPhase,
                waterLevel: waterLevel?.waterLevelCm,
                moisture: moistureReading?.moisturePercent
            }, 'AWD control decision made');
            return decision;
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId }, 'Failed to make control decision');
            throw error;
        }
    }
    async executeIrrigation(fieldId, decision) {
        try {
            if (decision.action !== 'start_irrigation') {
                return { success: false, reason: 'Not an irrigation decision' };
            }
            const optimalParams = await irrigation_learning_service_1.irrigationLearningService.getOptimalParameters(fieldId);
            const currentLevel = await sensor_management_service_1.sensorManagementService.getCurrentWaterLevel(fieldId);
            if (!currentLevel) {
                throw new Error('Cannot read current water level');
            }
            const irrigationStatus = await irrigation_controller_service_1.irrigationControllerService.startIrrigation({
                fieldId,
                targetLevelCm: decision.targetWaterLevel || 10,
                toleranceCm: optimalParams.toleranceCm,
                maxDurationMinutes: optimalParams.maxDurationMinutes,
                sensorCheckIntervalSeconds: optimalParams.sensorCheckInterval,
                minFlowRateCmPerMin: optimalParams.minFlowRateThreshold,
                emergencyStopLevel: 15
            });
            await (0, kafka_1.publishMessage)(kafka_1.KafkaTopics.AWD_IRRIGATION_EVENTS, {
                type: 'irrigation_started',
                fieldId,
                scheduleId: irrigationStatus.scheduleId,
                targetLevel: decision.targetWaterLevel,
                estimatedDuration: decision.estimatedDuration,
                method: 'water_level_based',
                timestamp: new Date().toISOString()
            }, fieldId);
            return {
                success: true,
                scheduleId: irrigationStatus.scheduleId,
                status: irrigationStatus,
                method: 'water_level_based'
            };
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId, decision }, 'Failed to execute irrigation');
            throw error;
        }
    }
    async getIrrigationStatus(fieldId) {
        try {
            const activeScheduleId = await this.getActiveIrrigationId(fieldId);
            if (activeScheduleId) {
                const status = await this.redis.get(`irrigation:status:${activeScheduleId}`);
                if (status) {
                    return {
                        active: true,
                        ...JSON.parse(status)
                    };
                }
            }
            const [waterLevel, config, patterns] = await Promise.all([
                sensor_management_service_1.sensorManagementService.getCurrentWaterLevel(fieldId),
                this.getFieldConfig(fieldId),
                irrigation_learning_service_1.irrigationLearningService.analyzeFieldPatterns(fieldId)
            ]);
            const recommendation = await this.getIrrigationRecommendation(fieldId, config, waterLevel?.waterLevelCm || 0);
            return {
                active: false,
                fieldId,
                currentWaterLevel: waterLevel?.waterLevelCm,
                currentPhase: config?.currentPhase,
                patterns,
                recommendation
            };
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId }, 'Failed to get irrigation status');
            throw error;
        }
    }
    async stopIrrigation(fieldId, reason) {
        try {
            const activeScheduleId = await this.getActiveIrrigationId(fieldId);
            if (!activeScheduleId) {
                return { success: false, reason: 'No active irrigation found' };
            }
            await irrigation_controller_service_1.irrigationControllerService.stopIrrigation(activeScheduleId, reason);
            await (0, kafka_1.publishMessage)(kafka_1.KafkaTopics.AWD_IRRIGATION_EVENTS, {
                type: 'irrigation_stopped',
                fieldId,
                scheduleId: activeScheduleId,
                reason,
                timestamp: new Date().toISOString()
            }, fieldId);
            return {
                success: true,
                scheduleId: activeScheduleId,
                reason
            };
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId }, 'Failed to stop irrigation');
            throw error;
        }
    }
    async enhanceIrrigationDecision(fieldId, baseDecision, currentLevel) {
        try {
            const prediction = await irrigation_learning_service_1.irrigationLearningService.predictIrrigationPerformance(fieldId, {
                initialLevel: currentLevel,
                targetLevel: baseDecision.targetWaterLevel || 10,
                soilType: await this.getFieldSoilType(fieldId),
                temperature: await this.getCurrentTemperature(fieldId),
                humidity: await this.getCurrentHumidity(fieldId),
                lastIrrigationDays: await this.getDaysSinceLastIrrigation(fieldId),
                concurrentIrrigations: await this.getConcurrentIrrigations(),
                season: this.getCurrentSeason()
            });
            const recommendation = await irrigation_learning_service_1.irrigationLearningService.getIrrigationRecommendation(fieldId, baseDecision.targetWaterLevel || 10);
            return {
                ...baseDecision,
                estimatedDuration: prediction.predictions.estimatedDuration,
                metadata: {
                    method: 'water_level_based',
                    prediction: {
                        duration: prediction.predictions.estimatedDuration,
                        flowRate: prediction.predictions.expectedFlowRate,
                        waterVolume: prediction.predictions.waterVolume,
                        confidence: prediction.predictions.confidenceLevel,
                        basedOnSamples: prediction.basedOnSamples
                    },
                    recommendation: {
                        startTime: recommendation.recommendedStartTime,
                        confidence: recommendation.confidence
                    }
                }
            };
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId }, 'Failed to enhance irrigation decision');
            return baseDecision;
        }
    }
    async getIrrigationRecommendation(fieldId, config, currentLevel) {
        if (!config)
            return null;
        const schedule = this.getScheduleTemplate(config.plantingMethod);
        const currentPhaseInfo = this.getCurrentPhase(schedule, config.currentWeek);
        const needsIrrigation = currentLevel < currentPhaseInfo.targetWaterLevel - 2;
        if (!needsIrrigation) {
            return {
                action: 'maintain',
                reason: 'Water level within acceptable range',
                nextCheck: new Date(Date.now() + 24 * 60 * 60 * 1000)
            };
        }
        const prediction = await irrigation_learning_service_1.irrigationLearningService.getIrrigationRecommendation(fieldId, currentPhaseInfo.targetWaterLevel);
        return {
            action: 'irrigate',
            targetLevel: currentPhaseInfo.targetWaterLevel,
            estimatedDuration: prediction.estimatedDuration,
            recommendedStartTime: prediction.recommendedStartTime,
            expectedFlowRate: prediction.expectedFlowRate,
            confidence: prediction.confidence,
            reason: `Water level (${currentLevel}cm) below target (${currentPhaseInfo.targetWaterLevel}cm)`
        };
    }
    async getActiveIrrigationId(fieldId) {
        const key = `irrigation:field:${fieldId}`;
        return await this.redis.get(key);
    }
    async getActiveIrrigation(fieldId) {
        const scheduleId = await this.getActiveIrrigationId(fieldId);
        if (!scheduleId)
            return null;
        const statusKey = `irrigation:status:${scheduleId}`;
        const status = await this.redis.get(statusKey);
        return status ? JSON.parse(status) : null;
    }
    async getFieldSoilType(fieldId) {
        const result = await this.postgresPool.query('SELECT soil_type FROM awd.awd_fields WHERE id = $1', [fieldId]);
        return result.rows[0]?.soil_type || 'loam';
    }
    async getCurrentTemperature(fieldId) {
        try {
            const weather = await weather_integration_1.weatherIntegration.getCurrentWeather(fieldId);
            return weather?.temperature || 28;
        }
        catch {
            return 28;
        }
    }
    async getCurrentHumidity(fieldId) {
        try {
            const weather = await weather_integration_1.weatherIntegration.getCurrentWeather(fieldId);
            return weather?.humidity || 70;
        }
        catch {
            return 70;
        }
    }
    async getDaysSinceLastIrrigation(fieldId) {
        const result = await this.postgresPool.query(`
      SELECT MAX(actual_end) as last_irrigation
      FROM awd.irrigation_schedules
      WHERE field_id = $1 AND status = 'completed'
    `, [fieldId]);
        if (result.rows[0]?.last_irrigation) {
            const daysSince = (Date.now() - new Date(result.rows[0].last_irrigation).getTime()) / (1000 * 60 * 60 * 24);
            return Math.round(daysSince);
        }
        return 7;
    }
    async getConcurrentIrrigations() {
        const result = await this.postgresPool.query(`
      SELECT COUNT(*) as count
      FROM awd.irrigation_schedules
      WHERE status = 'active'
    `);
        return parseInt(result.rows[0]?.count || '0');
    }
    getCurrentSeason() {
        const month = new Date().getMonth();
        if (month >= 10 || month <= 1)
            return 'dry';
        if (month >= 5 && month <= 9)
            return 'wet';
        return 'normal';
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
    getScheduleTemplate(plantingMethod) {
        return plantingMethod === 'transplanted'
            ? awd_control_types_1.TRANSPLANTED_SCHEDULE
            : awd_control_types_1.DIRECT_SEEDED_SCHEDULE;
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
                notifications
            };
        }
    }
    evaluateDryingPhase(config, currentWaterLevel, moisturePercent, sensorCheck, notifications) {
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
}
exports.AWDControlServiceV2 = AWDControlServiceV2;
exports.awdControlServiceV2 = new AWDControlServiceV2();
//# sourceMappingURL=awd-control-v2.service.js.map