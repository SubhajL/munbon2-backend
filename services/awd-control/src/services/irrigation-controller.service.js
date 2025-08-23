"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.irrigationControllerService = exports.IrrigationControllerService = void 0;
const database_1 = require("../config/database");
const redis_1 = require("../config/redis");
const logger_1 = require("../utils/logger");
const kafka_1 = require("../config/kafka");
const sensor_management_service_1 = require("./sensor-management.service");
const uuid_1 = require("uuid");
class IrrigationControllerService {
    postgresPool = (0, database_1.getPostgresPool)();
    timescalePool = (0, database_1.getTimescalePool)();
    redis = (0, redis_1.getRedisClient)();
    DEFAULT_TOLERANCE_CM = 1.0;
    DEFAULT_CHECK_INTERVAL_SEC = 300;
    DEFAULT_MAX_DURATION_MIN = 1440;
    MIN_FLOW_RATE_CM_PER_MIN = 0.05;
    NO_RISE_THRESHOLD_CHECKS = 3;
    RAPID_DROP_THRESHOLD_CM = 2;
    activeIrrigations = new Map();
    async startIrrigation(config) {
        const scheduleId = (0, uuid_1.v4)();
        const startTime = new Date();
        try {
            const initialLevel = await this.getCurrentWaterLevel(config.fieldId);
            if (!initialLevel) {
                throw new Error('Cannot read initial water level');
            }
            const existingIrrigation = await this.getActiveIrrigation(config.fieldId);
            if (existingIrrigation) {
                throw new Error(`Field ${config.fieldId} already has active irrigation`);
            }
            await this.createIrrigationSchedule({
                scheduleId,
                fieldId: config.fieldId,
                targetLevel: config.targetLevelCm,
                initialLevel: initialLevel.waterLevelCm,
                startTime
            });
            await this.controlGates(config.fieldId, 'open');
            const monitorInterval = this.startMonitoring(scheduleId, config);
            this.activeIrrigations.set(scheduleId, monitorInterval);
            const status = {
                scheduleId,
                fieldId: config.fieldId,
                status: 'active',
                startTime,
                currentLevelCm: initialLevel.waterLevelCm,
                targetLevelCm: config.targetLevelCm,
                flowRateCmPerMin: 0,
                anomaliesDetected: 0
            };
            await this.updateIrrigationStatus(status);
            logger_1.logger.info({
                scheduleId,
                fieldId: config.fieldId,
                initialLevel: initialLevel.waterLevelCm,
                targetLevel: config.targetLevelCm
            }, 'Started water level-based irrigation');
            return status;
        }
        catch (error) {
            logger_1.logger.error({ error, config }, 'Failed to start irrigation');
            throw error;
        }
    }
    startMonitoring(scheduleId, config) {
        let previousLevel = config.targetLevelCm;
        let previousTime = Date.now();
        let noRiseCount = 0;
        let totalVolume = 0;
        const levelHistory = [];
        const monitoringInterval = setInterval(async () => {
            try {
                const currentReading = await this.getCurrentWaterLevel(config.fieldId);
                if (!currentReading) {
                    await this.handleSensorFailure(scheduleId, config.fieldId);
                    return;
                }
                const currentLevel = currentReading.waterLevelCm;
                const currentTime = Date.now();
                const timeDeltaMin = (currentTime - previousTime) / 60000;
                const levelChange = currentLevel - previousLevel;
                const flowRate = timeDeltaMin > 0 ? levelChange / timeDeltaMin : 0;
                await this.recordMonitoringData({
                    scheduleId,
                    fieldId: config.fieldId,
                    waterLevel: currentLevel,
                    flowRate,
                    sensorId: currentReading.sensorId,
                    timestamp: new Date()
                });
                levelHistory.push({ time: new Date(), level: currentLevel });
                if (levelHistory.length > 10)
                    levelHistory.shift();
                const anomalies = await this.detectAnomalies({
                    scheduleId,
                    fieldId: config.fieldId,
                    currentLevel,
                    previousLevel,
                    flowRate,
                    levelHistory,
                    noRiseCount,
                    targetLevel: config.targetLevelCm
                });
                for (const anomaly of anomalies) {
                    await this.handleAnomaly(scheduleId, config.fieldId, anomaly);
                    if (anomaly.severity === 'critical') {
                        await this.stopIrrigation(scheduleId, 'anomaly_detected');
                        return;
                    }
                }
                if (currentLevel >= config.targetLevelCm - config.toleranceCm) {
                    await this.completeIrrigation(scheduleId, {
                        achievedLevel: currentLevel,
                        totalDuration: (Date.now() - previousTime) / 60000,
                        totalVolume,
                        avgFlowRate: totalVolume / ((Date.now() - previousTime) / 60000)
                    });
                    return;
                }
                if (flowRate < config.minFlowRateCmPerMin) {
                    noRiseCount++;
                    if (noRiseCount >= this.NO_RISE_THRESHOLD_CHECKS) {
                        await this.handleAnomaly(scheduleId, config.fieldId, {
                            type: 'no_rise',
                            severity: 'critical',
                            description: `No water level rise detected after ${noRiseCount} checks`,
                            metrics: { flowRate, currentLevel }
                        });
                    }
                }
                else {
                    noRiseCount = 0;
                }
                const elapsedMinutes = (Date.now() - new Date(await this.getStartTime(scheduleId)).getTime()) / 60000;
                if (elapsedMinutes > config.maxDurationMinutes) {
                    await this.stopIrrigation(scheduleId, 'timeout');
                    return;
                }
                await this.updateIrrigationStatus({
                    scheduleId,
                    fieldId: config.fieldId,
                    status: 'active',
                    startTime: new Date(await this.getStartTime(scheduleId)),
                    currentLevelCm: currentLevel,
                    targetLevelCm: config.targetLevelCm,
                    flowRateCmPerMin: flowRate,
                    estimatedCompletionTime: this.estimateCompletionTime(currentLevel, config.targetLevelCm, flowRate),
                    anomaliesDetected: anomalies.length
                });
                totalVolume += levelChange * 10000;
                previousLevel = currentLevel;
                previousTime = currentTime;
            }
            catch (error) {
                logger_1.logger.error({ error, scheduleId }, 'Error in irrigation monitoring');
                await this.handleMonitoringError(scheduleId, config.fieldId, error);
            }
        }, config.sensorCheckIntervalSeconds * 1000);
        return monitoringInterval;
    }
    async detectAnomalies(params) {
        const anomalies = [];
        if (params.flowRate < this.MIN_FLOW_RATE_CM_PER_MIN && params.flowRate >= 0) {
            anomalies.push({
                type: 'low_flow',
                severity: 'warning',
                description: `Flow rate (${params.flowRate.toFixed(3)} cm/min) below minimum`,
                metrics: {
                    flowRate: params.flowRate,
                    threshold: this.MIN_FLOW_RATE_CM_PER_MIN
                }
            });
        }
        if (params.currentLevel < params.previousLevel - this.RAPID_DROP_THRESHOLD_CM) {
            anomalies.push({
                type: 'rapid_drop',
                severity: 'critical',
                description: `Water level dropped ${(params.previousLevel - params.currentLevel).toFixed(2)}cm - possible leak`,
                metrics: {
                    previousLevel: params.previousLevel,
                    currentLevel: params.currentLevel,
                    drop: params.previousLevel - params.currentLevel
                }
            });
        }
        if (params.noRiseCount >= this.NO_RISE_THRESHOLD_CHECKS) {
            anomalies.push({
                type: 'no_rise',
                severity: 'critical',
                description: 'No water level rise detected - possible gate or pump failure',
                metrics: {
                    checksWithoutRise: params.noRiseCount,
                    currentLevel: params.currentLevel
                }
            });
        }
        if (params.currentLevel > params.targetLevel + 5) {
            anomalies.push({
                type: 'overflow_risk',
                severity: 'critical',
                description: 'Water level exceeding target by more than 5cm',
                metrics: {
                    currentLevel: params.currentLevel,
                    targetLevel: params.targetLevel,
                    excess: params.currentLevel - params.targetLevel
                }
            });
        }
        for (const anomaly of anomalies) {
            await this.recordAnomaly(params.scheduleId, params.fieldId, anomaly);
        }
        return anomalies;
    }
    async handleAnomaly(scheduleId, fieldId, anomaly) {
        logger_1.logger.warn({ scheduleId, fieldId, anomaly }, 'Anomaly detected during irrigation');
        await (0, kafka_1.publishMessage)(kafka_1.KafkaTopics.ALERT_NOTIFICATIONS, {
            type: 'irrigation_anomaly',
            scheduleId,
            fieldId,
            anomaly,
            timestamp: new Date().toISOString()
        });
        switch (anomaly.type) {
            case 'rapid_drop':
            case 'overflow_risk':
                await this.stopIrrigation(scheduleId, 'anomaly_critical');
                break;
            case 'low_flow':
                await this.adjustGateFlow(fieldId, 'increase');
                break;
            case 'no_rise':
                await this.attemptRecovery(scheduleId, fieldId);
                break;
            case 'sensor_failure':
                await this.switchToBackupSensor(fieldId);
                break;
        }
    }
    async completeIrrigation(scheduleId, results) {
        try {
            const interval = this.activeIrrigations.get(scheduleId);
            if (interval) {
                clearInterval(interval);
                this.activeIrrigations.delete(scheduleId);
            }
            const status = await this.getIrrigationStatus(scheduleId);
            if (status) {
                await this.controlGates(status.fieldId, 'close');
            }
            await this.updateIrrigationSchedule(scheduleId, {
                status: 'completed',
                endTime: new Date(),
                finalLevel: results.achievedLevel,
                waterVolume: results.totalVolume,
                avgFlowRate: results.avgFlowRate
            });
            await this.recordPerformanceMetrics(scheduleId, results);
            await this.updateLearningModel(scheduleId);
            logger_1.logger.info({
                scheduleId,
                results
            }, 'Irrigation completed successfully');
        }
        catch (error) {
            logger_1.logger.error({ error, scheduleId }, 'Error completing irrigation');
            throw error;
        }
    }
    async stopIrrigation(scheduleId, reason) {
        try {
            const interval = this.activeIrrigations.get(scheduleId);
            if (interval) {
                clearInterval(interval);
                this.activeIrrigations.delete(scheduleId);
            }
            const status = await this.getIrrigationStatus(scheduleId);
            if (!status)
                return;
            await this.controlGates(status.fieldId, 'close');
            await this.updateIrrigationSchedule(scheduleId, {
                status: reason === 'anomaly_critical' ? 'failed' : 'cancelled',
                endTime: new Date(),
                finalLevel: status.currentLevelCm
            });
            logger_1.logger.info({
                scheduleId,
                fieldId: status.fieldId,
                reason
            }, 'Irrigation stopped');
        }
        catch (error) {
            logger_1.logger.error({ error, scheduleId }, 'Error stopping irrigation');
            throw error;
        }
    }
    estimateCompletionTime(currentLevel, targetLevel, flowRate) {
        if (flowRate <= 0)
            return undefined;
        const remainingCm = targetLevel - currentLevel;
        const remainingMinutes = remainingCm / flowRate;
        const completionTime = new Date();
        completionTime.setMinutes(completionTime.getMinutes() + remainingMinutes);
        return completionTime;
    }
    async getCurrentWaterLevel(fieldId) {
        return await sensor_management_service_1.sensorManagementService.getCurrentWaterLevel(fieldId);
    }
    async controlGates(fieldId, action) {
        try {
            const gates = await this.getFieldGates(fieldId);
            for (const gate of gates) {
                await this.sendGateCommand(gate.gateId, action);
                await this.postgresPool.query(`
          INSERT INTO awd.gate_control_logs 
          (field_id, gate_id, action, requested_at, executed_at, success)
          VALUES ($1, $2, $3, NOW(), NOW(), true)
        `, [fieldId, gate.gateId, action]);
            }
            await (0, kafka_1.publishMessage)(kafka_1.KafkaTopics.GATE_CONTROL_COMMANDS, {
                fieldId,
                gates: gates.map(g => g.gateId),
                action,
                timestamp: new Date().toISOString()
            });
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId, action }, 'Failed to control gates');
            throw error;
        }
    }
    async createIrrigationSchedule(params) {
        await this.postgresPool.query(`
      INSERT INTO awd.irrigation_schedules
      (id, field_id, scheduled_start, target_level_cm, initial_level_cm, status)
      VALUES ($1, $2, $3, $4, $5, 'active')
    `, [params.scheduleId, params.fieldId, params.startTime, params.targetLevel, params.initialLevel]);
    }
    async updateIrrigationSchedule(scheduleId, updates) {
        const setClauses = [];
        const values = [scheduleId];
        let paramCount = 1;
        if (updates.status) {
            setClauses.push(`status = $${++paramCount}`);
            values.push(updates.status);
        }
        if (updates.endTime) {
            setClauses.push(`actual_end = $${++paramCount}`);
            values.push(updates.endTime);
        }
        if (updates.finalLevel !== undefined) {
            setClauses.push(`final_level_cm = $${++paramCount}`);
            values.push(updates.finalLevel);
        }
        if (updates.waterVolume !== undefined) {
            setClauses.push(`water_volume_liters = $${++paramCount}`);
            values.push(updates.waterVolume);
        }
        if (updates.avgFlowRate !== undefined) {
            setClauses.push(`avg_flow_rate_cm_per_min = $${++paramCount}`);
            values.push(updates.avgFlowRate);
        }
        await this.postgresPool.query(`
      UPDATE awd.irrigation_schedules
      SET ${setClauses.join(', ')}, updated_at = CURRENT_TIMESTAMP
      WHERE id = $1
    `, values);
    }
    async recordMonitoringData(data) {
        await this.postgresPool.query(`
      INSERT INTO awd.irrigation_monitoring
      (schedule_id, field_id, timestamp, water_level_cm, flow_rate_cm_per_min, sensor_id)
      VALUES ($1, $2, $3, $4, $5, $6)
    `, [data.scheduleId, data.fieldId, data.timestamp, data.waterLevel, data.flowRate, data.sensorId]);
    }
    async recordAnomaly(scheduleId, fieldId, anomaly) {
        await this.postgresPool.query(`
      INSERT INTO awd.irrigation_anomalies
      (schedule_id, field_id, detected_at, anomaly_type, severity, description, metrics)
      VALUES ($1, $2, NOW(), $3, $4, $5, $6)
    `, [scheduleId, fieldId, anomaly.type, anomaly.severity, anomaly.description, JSON.stringify(anomaly.metrics)]);
    }
    async recordPerformanceMetrics(scheduleId, results) {
        const irrigationData = await this.postgresPool.query(`
      SELECT * FROM awd.irrigation_schedules WHERE id = $1
    `, [scheduleId]);
        const schedule = irrigationData.rows[0];
        const targetAchieved = Math.abs(results.achievedLevel - schedule.target_level_cm) < 1;
        const timeEfficiency = results.totalDuration < 360 ? 1 : 360 / results.totalDuration;
        const efficiencyScore = (targetAchieved ? 0.7 : 0.3) + (timeEfficiency * 0.3);
        await this.postgresPool.query(`
      INSERT INTO awd.irrigation_performance
      (field_id, schedule_id, start_time, end_time, initial_level_cm, target_level_cm, 
       achieved_level_cm, total_duration_minutes, water_volume_liters, avg_flow_rate_cm_per_min,
       efficiency_score)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
    `, [
            schedule.field_id, scheduleId, schedule.scheduled_start, new Date(),
            schedule.initial_level_cm, schedule.target_level_cm, results.achievedLevel,
            results.totalDuration, results.totalVolume, results.avgFlowRate,
            efficiencyScore
        ]);
    }
    async updateLearningModel(scheduleId) {
        logger_1.logger.info({ scheduleId }, 'Updating ML model with irrigation results');
    }
    async getIrrigationStatus(scheduleId) {
        const key = `irrigation:status:${scheduleId}`;
        const data = await this.redis.get(key);
        return data ? JSON.parse(data) : null;
    }
    async updateIrrigationStatus(status) {
        const key = `irrigation:status:${status.scheduleId}`;
        await this.redis.setex(key, 86400, JSON.stringify(status));
        const fieldKey = `irrigation:field:${status.fieldId}`;
        await this.redis.setex(fieldKey, 86400, status.scheduleId);
    }
    async getActiveIrrigation(fieldId) {
        const key = `irrigation:field:${fieldId}`;
        return await this.redis.get(key);
    }
    async getStartTime(scheduleId) {
        const status = await this.getIrrigationStatus(scheduleId);
        return status ? new Date(status.startTime).getTime() : Date.now();
    }
    async handleSensorFailure(scheduleId, fieldId) {
        await this.handleAnomaly(scheduleId, fieldId, {
            type: 'sensor_failure',
            severity: 'critical',
            description: 'Cannot read water level sensor',
            metrics: { lastReadTime: new Date() }
        });
    }
    async handleMonitoringError(scheduleId, fieldId, error) {
        logger_1.logger.error({ error, scheduleId, fieldId }, 'Monitoring error occurred');
    }
    async attemptRecovery(scheduleId, fieldId) {
        logger_1.logger.info({ scheduleId, fieldId }, 'Attempting irrigation recovery');
    }
    async switchToBackupSensor(fieldId) {
        logger_1.logger.info({ fieldId }, 'Switching to backup water level source');
    }
    async adjustGateFlow(fieldId, direction) {
        logger_1.logger.info({ fieldId, direction }, 'Adjusting gate flow rate');
    }
    async getFieldGates(fieldId) {
        return [{ gateId: `GATE_${fieldId}_1` }];
    }
    async sendGateCommand(gateId, action) {
        logger_1.logger.info({ gateId, action }, 'Sending gate control command');
    }
    async getIrrigationRecommendation(fieldId, targetLevel) {
        try {
            const history = await this.postgresPool.query(`
        SELECT 
          AVG(total_duration_minutes) as avg_duration,
          AVG(avg_flow_rate_cm_per_min) as avg_flow_rate,
          COUNT(*) as sample_size,
          STDDEV(total_duration_minutes) as duration_stddev
        FROM awd.irrigation_performance
        WHERE field_id = $1
          AND target_level_cm = $2
          AND efficiency_score > 0.7
          AND start_time > NOW() - INTERVAL '30 days'
      `, [fieldId, targetLevel]);
            if (history.rows.length === 0 || history.rows[0].sample_size < 3) {
                return {
                    estimatedDuration: (targetLevel - 0) * 60,
                    recommendedStartTime: new Date(),
                    expectedFlowRate: 0.1,
                    confidence: 0.3
                };
            }
            const data = history.rows[0];
            const confidence = Math.min(0.9, 0.3 + (data.sample_size * 0.1));
            return {
                estimatedDuration: Math.round(data.avg_duration),
                recommendedStartTime: this.calculateOptimalStartTime(fieldId),
                expectedFlowRate: parseFloat(data.avg_flow_rate),
                confidence
            };
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId }, 'Failed to get irrigation recommendation');
            throw error;
        }
    }
    calculateOptimalStartTime(fieldId) {
        const startTime = new Date();
        startTime.setHours(6, 0, 0, 0);
        return startTime;
    }
}
exports.IrrigationControllerService = IrrigationControllerService;
exports.irrigationControllerService = new IrrigationControllerService();
//# sourceMappingURL=irrigation-controller.service.js.map