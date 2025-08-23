"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.irrigationLearningService = exports.IrrigationLearningService = void 0;
const database_1 = require("../config/database");
const logger_1 = require("../utils/logger");
class IrrigationLearningService {
    postgresPool = (0, database_1.getPostgresPool)();
    MODEL_VERSION = '1.0.0';
    MIN_SAMPLES_FOR_PREDICTION = 5;
    RECENT_DAYS_WEIGHT = 0.7;
    SEASONAL_ADJUSTMENT = {
        dry: 1.2,
        wet: 0.9,
        normal: 1.0
    };
    async predictIrrigationPerformance(fieldId, conditions) {
        try {
            const historicalData = await this.getHistoricalPerformance(fieldId, conditions);
            if (historicalData.length < this.MIN_SAMPLES_FOR_PREDICTION) {
                return this.getDefaultPrediction(fieldId, conditions);
            }
            const predictions = this.calculateWeightedPredictions(historicalData, conditions);
            predictions.estimatedDuration *= this.SEASONAL_ADJUSTMENT[conditions.season] || 1.0;
            await this.storePrediction(fieldId, conditions, predictions);
            return {
                fieldId,
                conditions,
                predictions,
                modelVersion: this.MODEL_VERSION,
                basedOnSamples: historicalData.length
            };
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId }, 'Failed to predict irrigation performance');
            return this.getDefaultPrediction(fieldId, conditions);
        }
    }
    async analyzeFieldPatterns(fieldId) {
        try {
            const patterns = [];
            const flowRatePattern = await this.analyzeFlowRatePattern(fieldId);
            if (flowRatePattern)
                patterns.push(flowRatePattern);
            const timePattern = await this.analyzeTimeOfDayPattern(fieldId);
            if (timePattern)
                patterns.push(timePattern);
            const anomalyPattern = await this.analyzeAnomalyPattern(fieldId);
            if (anomalyPattern)
                patterns.push(anomalyPattern);
            const efficiencyTrend = await this.analyzeEfficiencyTrend(fieldId);
            if (efficiencyTrend)
                patterns.push(efficiencyTrend);
            return patterns;
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId }, 'Failed to analyze field patterns');
            return [];
        }
    }
    async updateModelWithResults(scheduleId) {
        try {
            const results = await this.postgresPool.query(`
        SELECT 
          s.field_id,
          s.initial_level_cm,
          s.target_level_cm,
          s.actual_end - s.scheduled_start as duration,
          s.water_volume_liters,
          s.avg_flow_rate_cm_per_min,
          p.efficiency_score,
          p.anomalies_detected,
          COUNT(a.id) as total_anomalies
        FROM awd.irrigation_schedules s
        LEFT JOIN awd.irrigation_performance p ON s.id = p.schedule_id
        LEFT JOIN awd.irrigation_anomalies a ON s.id = a.schedule_id
        WHERE s.id = $1
        GROUP BY s.field_id, s.initial_level_cm, s.target_level_cm, 
                 s.actual_end, s.scheduled_start, s.water_volume_liters,
                 s.avg_flow_rate_cm_per_min, p.efficiency_score, p.anomalies_detected
      `, [scheduleId]);
            if (results.rows.length === 0)
                return;
            const data = results.rows[0];
            const features = await this.extractFeatures(data);
            await this.updateFieldModel(data.field_id, features);
            if (data.efficiency_score > 0.8 || data.total_anomalies > 2) {
                await this.updateGlobalModel(features);
            }
            logger_1.logger.info({ scheduleId, fieldId: data.field_id }, 'Model updated with irrigation results');
        }
        catch (error) {
            logger_1.logger.error({ error, scheduleId }, 'Failed to update model');
        }
    }
    async getOptimalParameters(fieldId) {
        try {
            const fieldData = await this.postgresPool.query(`
        SELECT 
          AVG(p.total_duration_minutes) as avg_duration,
          STDDEV(p.total_duration_minutes) as duration_stddev,
          AVG(p.avg_flow_rate_cm_per_min) as avg_flow_rate,
          MIN(p.avg_flow_rate_cm_per_min) as min_flow_rate,
          COUNT(DISTINCT a.id) as anomaly_count,
          COUNT(DISTINCT p.id) as irrigation_count
        FROM awd.irrigation_performance p
        LEFT JOIN awd.irrigation_anomalies a ON p.schedule_id = a.schedule_id
        WHERE p.field_id = $1
          AND p.efficiency_score > 0.6
          AND p.start_time > NOW() - INTERVAL '60 days'
      `, [fieldId]);
            const data = fieldData.rows[0];
            if (!data || data.irrigation_count < 5) {
                return {
                    sensorCheckInterval: 300,
                    minFlowRateThreshold: 0.05,
                    maxDurationMinutes: 1440,
                    toleranceCm: 1.0
                };
            }
            const avgDuration = parseFloat(data.avg_duration) || 360;
            const stdDev = parseFloat(data.duration_stddev) || 60;
            const minFlowRate = parseFloat(data.min_flow_rate) || 0.05;
            return {
                sensorCheckInterval: this.calculateOptimalCheckInterval(avgDuration),
                minFlowRateThreshold: Math.max(0.03, minFlowRate * 0.8),
                maxDurationMinutes: Math.round(avgDuration + (2 * stdDev)),
                toleranceCm: data.anomaly_count > 5 ? 0.5 : 1.0
            };
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId }, 'Failed to get optimal parameters');
            return {
                sensorCheckInterval: 300,
                minFlowRateThreshold: 0.05,
                maxDurationMinutes: 1440,
                toleranceCm: 1.0
            };
        }
    }
    async getHistoricalPerformance(fieldId, conditions) {
        const query = `
      SELECT 
        p.*,
        s.initial_level_cm,
        s.target_level_cm,
        s.scheduled_start,
        EXTRACT(EPOCH FROM (p.end_time - p.start_time))/60 as duration_minutes
      FROM awd.irrigation_performance p
      JOIN awd.irrigation_schedules s ON p.schedule_id = s.id
      WHERE p.field_id = $1
        AND ABS(s.initial_level_cm - $2) < 3  -- Similar initial level
        AND ABS(s.target_level_cm - $3) < 2   -- Similar target
        AND p.efficiency_score > 0.5
        AND p.start_time > NOW() - INTERVAL '90 days'
      ORDER BY p.start_time DESC
      LIMIT 20
    `;
        const result = await this.postgresPool.query(query, [
            fieldId,
            conditions.initialLevel,
            conditions.targetLevel
        ]);
        return result.rows;
    }
    calculateWeightedPredictions(historicalData, conditions) {
        const now = new Date();
        let totalWeight = 0;
        let weightedDuration = 0;
        let weightedFlowRate = 0;
        let weightedVolume = 0;
        historicalData.forEach(record => {
            const daysAgo = (now.getTime() - new Date(record.start_time).getTime()) / (1000 * 60 * 60 * 24);
            const recencyWeight = Math.exp(-daysAgo / 30);
            const levelDiff = Math.abs(record.initial_level_cm - conditions.initialLevel);
            const similarityWeight = Math.exp(-levelDiff / 5);
            const weight = recencyWeight * similarityWeight * record.efficiency_score;
            totalWeight += weight;
            weightedDuration += record.duration_minutes * weight;
            weightedFlowRate += record.avg_flow_rate_cm_per_min * weight;
            weightedVolume += record.water_volume_liters * weight;
        });
        if (totalWeight === 0) {
            return this.getDefaultValues(conditions);
        }
        const avgDuration = weightedDuration / totalWeight;
        const avgFlowRate = weightedFlowRate / totalWeight;
        const avgVolume = weightedVolume / totalWeight;
        let varianceSum = 0;
        historicalData.forEach(record => {
            const diff = record.duration_minutes - avgDuration;
            varianceSum += diff * diff;
        });
        const stdDev = Math.sqrt(varianceSum / historicalData.length);
        const confidence = Math.min(0.95, 0.5 + (historicalData.length * 0.05));
        return {
            estimatedDuration: Math.round(avgDuration),
            expectedFlowRate: avgFlowRate,
            waterVolume: Math.round(avgVolume),
            confidenceLevel: confidence,
            confidenceIntervalLower: Math.round(avgDuration - (1.96 * stdDev)),
            confidenceIntervalUpper: Math.round(avgDuration + (1.96 * stdDev))
        };
    }
    getDefaultPrediction(fieldId, conditions) {
        const depthNeeded = conditions.targetLevel - conditions.initialLevel;
        const estimatedDuration = depthNeeded * 60;
        return {
            fieldId,
            conditions,
            predictions: {
                estimatedDuration,
                expectedFlowRate: 0.0167,
                waterVolume: depthNeeded * 10000,
                confidenceLevel: 0.3,
                confidenceIntervalLower: estimatedDuration * 0.7,
                confidenceIntervalUpper: estimatedDuration * 1.5
            },
            modelVersion: this.MODEL_VERSION,
            basedOnSamples: 0
        };
    }
    getDefaultValues(conditions) {
        const depthNeeded = conditions.targetLevel - conditions.initialLevel;
        return {
            estimatedDuration: depthNeeded * 60,
            expectedFlowRate: 0.0167,
            waterVolume: depthNeeded * 10000,
            confidenceLevel: 0.3,
            confidenceIntervalLower: depthNeeded * 42,
            confidenceIntervalUpper: depthNeeded * 90
        };
    }
    async storePrediction(fieldId, conditions, predictions) {
        await this.postgresPool.query(`
      INSERT INTO awd.flow_rate_predictions
      (field_id, prediction_time, conditions, predicted_flow_rate, 
       confidence_interval_lower, confidence_interval_upper, model_version)
      VALUES ($1, NOW(), $2, $3, $4, $5, $6)
    `, [
            fieldId,
            JSON.stringify(conditions),
            predictions.expectedFlowRate,
            predictions.expectedFlowRate * 0.8,
            predictions.expectedFlowRate * 1.2,
            this.MODEL_VERSION
        ]);
    }
    async extractFeatures(data) {
        return {
            depthChange: data.target_level_cm - data.initial_level_cm,
            duration: data.duration,
            flowRate: data.avg_flow_rate_cm_per_min,
            efficiency: data.efficiency_score,
            anomalyRate: data.total_anomalies / (data.duration / 60),
            waterEfficiency: data.water_volume_liters / (data.target_level_cm - data.initial_level_cm)
        };
    }
    async updateFieldModel(fieldId, features) {
        logger_1.logger.debug({ fieldId, features }, 'Updating field model');
    }
    async updateGlobalModel(features) {
        logger_1.logger.debug({ features }, 'Updating global model');
    }
    calculateOptimalCheckInterval(avgDuration) {
        if (avgDuration < 120)
            return 180;
        if (avgDuration < 360)
            return 300;
        return 600;
    }
    async analyzeFlowRatePattern(fieldId) {
        const result = await this.postgresPool.query(`
      SELECT 
        AVG(avg_flow_rate_cm_per_min) as avg_flow,
        STDDEV(avg_flow_rate_cm_per_min) as flow_stddev,
        COUNT(*) as count
      FROM awd.irrigation_performance
      WHERE field_id = $1
        AND start_time > NOW() - INTERVAL '30 days'
    `, [fieldId]);
        const data = result.rows[0];
        if (!data || data.count < 5)
            return null;
        const avgFlow = parseFloat(data.avg_flow);
        const stdDev = parseFloat(data.flow_stddev);
        if (stdDev > avgFlow * 0.3) {
            return {
                fieldId,
                pattern: 'high_flow_variability',
                description: 'Flow rate varies significantly between irrigations',
                frequency: data.count,
                impact: 'negative',
                recommendations: [
                    'Check for partial gate blockages',
                    'Verify water pressure consistency',
                    'Consider gate maintenance'
                ]
            };
        }
        return null;
    }
    async analyzeTimeOfDayPattern(fieldId) {
        const result = await this.postgresPool.query(`
      SELECT 
        EXTRACT(HOUR FROM start_time) as hour,
        AVG(efficiency_score) as avg_efficiency,
        COUNT(*) as count
      FROM awd.irrigation_performance
      WHERE field_id = $1
        AND start_time > NOW() - INTERVAL '60 days'
      GROUP BY EXTRACT(HOUR FROM start_time)
      HAVING COUNT(*) > 2
      ORDER BY avg_efficiency DESC
    `, [fieldId]);
        if (result.rows.length < 3)
            return null;
        const bestHour = result.rows[0];
        const worstHour = result.rows[result.rows.length - 1];
        if (bestHour.avg_efficiency - worstHour.avg_efficiency > 0.2) {
            return {
                fieldId,
                pattern: 'time_dependent_efficiency',
                description: `Best performance at ${bestHour.hour}:00, worst at ${worstHour.hour}:00`,
                frequency: result.rows.reduce((sum, row) => sum + row.count, 0),
                impact: 'positive',
                recommendations: [
                    `Schedule irrigations around ${bestHour.hour}:00 for best efficiency`,
                    `Avoid irrigations at ${worstHour.hour}:00 when possible`
                ]
            };
        }
        return null;
    }
    async analyzeAnomalyPattern(fieldId) {
        const result = await this.postgresPool.query(`
      SELECT 
        anomaly_type,
        COUNT(*) as count,
        MAX(detected_at) as last_occurrence
      FROM awd.irrigation_anomalies
      WHERE field_id = $1
        AND detected_at > NOW() - INTERVAL '30 days'
      GROUP BY anomaly_type
      ORDER BY count DESC
    `, [fieldId]);
        if (result.rows.length === 0)
            return null;
        const totalAnomalies = result.rows.reduce((sum, row) => sum + parseInt(row.count), 0);
        const mostCommon = result.rows[0];
        if (totalAnomalies > 5) {
            return {
                fieldId,
                pattern: 'frequent_anomalies',
                description: `${mostCommon.anomaly_type} occurs most frequently (${mostCommon.count} times)`,
                frequency: totalAnomalies,
                impact: 'negative',
                recommendations: this.getAnomalyRecommendations(mostCommon.anomaly_type)
            };
        }
        return null;
    }
    async analyzeEfficiencyTrend(fieldId) {
        const result = await this.postgresPool.query(`
      SELECT 
        DATE_TRUNC('week', start_time) as week,
        AVG(efficiency_score) as avg_efficiency,
        COUNT(*) as count
      FROM awd.irrigation_performance
      WHERE field_id = $1
        AND start_time > NOW() - INTERVAL '90 days'
      GROUP BY DATE_TRUNC('week', start_time)
      ORDER BY week
    `, [fieldId]);
        if (result.rows.length < 4)
            return null;
        const firstHalf = result.rows.slice(0, Math.floor(result.rows.length / 2));
        const secondHalf = result.rows.slice(Math.floor(result.rows.length / 2));
        const firstAvg = firstHalf.reduce((sum, row) => sum + parseFloat(row.avg_efficiency), 0) / firstHalf.length;
        const secondAvg = secondHalf.reduce((sum, row) => sum + parseFloat(row.avg_efficiency), 0) / secondHalf.length;
        if (secondAvg > firstAvg + 0.1) {
            return {
                fieldId,
                pattern: 'improving_efficiency',
                description: 'Irrigation efficiency has improved over time',
                frequency: result.rows.reduce((sum, row) => sum + row.count, 0),
                impact: 'positive',
                recommendations: [
                    'Continue current practices',
                    'Document successful changes'
                ]
            };
        }
        else if (secondAvg < firstAvg - 0.1) {
            return {
                fieldId,
                pattern: 'declining_efficiency',
                description: 'Irrigation efficiency has declined over time',
                frequency: result.rows.reduce((sum, row) => sum + row.count, 0),
                impact: 'negative',
                recommendations: [
                    'Schedule equipment maintenance',
                    'Review recent system changes',
                    'Check for sensor calibration drift'
                ]
            };
        }
        return null;
    }
    getAnomalyRecommendations(anomalyType) {
        const recommendations = {
            'low_flow': [
                'Check for gate obstructions',
                'Verify pump operation',
                'Inspect canal water levels'
            ],
            'no_rise': [
                'Verify gate is actually opening',
                'Check for field drainage issues',
                'Inspect for breaches in field boundaries'
            ],
            'rapid_drop': [
                'Inspect field boundaries for leaks',
                'Check for excessive percolation',
                'Verify sensor accuracy'
            ],
            'sensor_failure': [
                'Schedule sensor maintenance',
                'Check battery levels',
                'Verify communication signal strength'
            ],
            'overflow_risk': [
                'Reduce gate opening percentage',
                'Implement staged irrigation',
                'Check field leveling'
            ]
        };
        return recommendations[anomalyType] || ['Review irrigation logs', 'Contact technical support'];
    }
}
exports.IrrigationLearningService = IrrigationLearningService;
exports.irrigationLearningService = new IrrigationLearningService();
//# sourceMappingURL=irrigation-learning.service.js.map