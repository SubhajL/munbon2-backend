"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const express_validator_1 = require("express-validator");
const awd_control_v2_service_1 = require("../services/awd-control-v2.service");
const irrigation_controller_service_1 = require("../services/irrigation-controller.service");
const irrigation_learning_service_1 = require("../services/irrigation-learning.service");
const logger_1 = require("../utils/logger");
const router = (0, express_1.Router)();
router.post('/fields/:fieldId/irrigation/start', [
    (0, express_validator_1.param)('fieldId').isUUID().withMessage('Invalid field ID'),
    (0, express_validator_1.body)('targetLevelCm').isFloat({ min: 1, max: 20 }).withMessage('Target level must be between 1-20cm'),
    (0, express_validator_1.body)('toleranceCm').optional().isFloat({ min: 0.1, max: 2 }).withMessage('Tolerance must be between 0.1-2cm'),
    (0, express_validator_1.body)('maxDurationHours').optional().isFloat({ min: 1, max: 48 }).withMessage('Max duration must be between 1-48 hours'),
    (0, express_validator_1.body)('emergencyStopLevel').optional().isFloat({ min: 10, max: 25 }).withMessage('Emergency stop level must be between 10-25cm')
], async (req, res) => {
    try {
        const errors = (0, express_validator_1.validationResult)(req);
        if (!errors.isEmpty()) {
            return res.status(400).json({ errors: errors.array() });
        }
        const { fieldId } = req.params;
        const decision = await awd_control_v2_service_1.awdControlServiceV2.makeControlDecision(fieldId);
        if (decision.action !== 'start_irrigation') {
            return res.status(409).json({
                success: false,
                reason: decision.reason,
                decision
            });
        }
        const customDecision = {
            ...decision,
            targetWaterLevel: req.body.targetLevelCm || decision.targetWaterLevel,
            maxDuration: (req.body.maxDurationHours || 24) * 60,
            emergencyStopLevel: req.body.emergencyStopLevel || 15
        };
        const result = await awd_control_v2_service_1.awdControlServiceV2.executeIrrigation(fieldId, customDecision);
        res.json({
            success: true,
            scheduleId: result.scheduleId,
            status: result.status,
            method: result.method,
            prediction: decision.metadata?.prediction,
            recommendation: decision.metadata?.recommendation
        });
    }
    catch (error) {
        logger_1.logger.error({ error, fieldId: req.params.fieldId }, 'Failed to start irrigation');
        res.status(500).json({ error: 'Failed to start irrigation' });
    }
});
router.get('/fields/:fieldId/irrigation/status', [
    (0, express_validator_1.param)('fieldId').isUUID().withMessage('Invalid field ID'),
    (0, express_validator_1.query)('includeHistory').optional().isBoolean().withMessage('includeHistory must be boolean')
], async (req, res) => {
    try {
        const errors = (0, express_validator_1.validationResult)(req);
        if (!errors.isEmpty()) {
            return res.status(400).json({ errors: errors.array() });
        }
        const { fieldId } = req.params;
        const status = await awd_control_v2_service_1.awdControlServiceV2.getIrrigationStatus(fieldId);
        if (req.query.includeHistory === 'true' && !status.active) {
            const history = await irrigation_learning_service_1.irrigationLearningService.analyzeFieldPatterns(fieldId);
            return res.json({
                ...status,
                history
            });
        }
        res.json(status);
    }
    catch (error) {
        logger_1.logger.error({ error, fieldId: req.params.fieldId }, 'Failed to get irrigation status');
        res.status(500).json({ error: 'Failed to get irrigation status' });
    }
});
router.post('/fields/:fieldId/irrigation/stop', [
    (0, express_validator_1.param)('fieldId').isUUID().withMessage('Invalid field ID'),
    (0, express_validator_1.body)('reason').isString().notEmpty().withMessage('Reason is required')
], async (req, res) => {
    try {
        const errors = (0, express_validator_1.validationResult)(req);
        if (!errors.isEmpty()) {
            return res.status(400).json({ errors: errors.array() });
        }
        const { fieldId } = req.params;
        const { reason } = req.body;
        const result = await awd_control_v2_service_1.awdControlServiceV2.stopIrrigation(fieldId, reason);
        res.json(result);
    }
    catch (error) {
        logger_1.logger.error({ error, fieldId: req.params.fieldId }, 'Failed to stop irrigation');
        res.status(500).json({ error: 'Failed to stop irrigation' });
    }
});
router.get('/fields/:fieldId/irrigation/recommendation', [
    (0, express_validator_1.param)('fieldId').isUUID().withMessage('Invalid field ID'),
    (0, express_validator_1.query)('targetLevel').optional().isFloat({ min: 1, max: 20 }).withMessage('Invalid target level')
], async (req, res) => {
    try {
        const errors = (0, express_validator_1.validationResult)(req);
        if (!errors.isEmpty()) {
            return res.status(400).json({ errors: errors.array() });
        }
        const { fieldId } = req.params;
        const targetLevel = req.query.targetLevel ? parseFloat(req.query.targetLevel) : 10;
        const recommendation = await irrigation_controller_service_1.irrigationControllerService.getIrrigationRecommendation(fieldId, targetLevel);
        res.json(recommendation);
    }
    catch (error) {
        logger_1.logger.error({ error, fieldId: req.params.fieldId }, 'Failed to get recommendation');
        res.status(500).json({ error: 'Failed to get recommendation' });
    }
});
router.get('/fields/:fieldId/irrigation/analytics', [
    (0, express_validator_1.param)('fieldId').isUUID().withMessage('Invalid field ID'),
    (0, express_validator_1.query)('days').optional().isInt({ min: 1, max: 365 }).withMessage('Days must be between 1-365')
], async (req, res) => {
    try {
        const errors = (0, express_validator_1.validationResult)(req);
        if (!errors.isEmpty()) {
            return res.status(400).json({ errors: errors.array() });
        }
        const { fieldId } = req.params;
        const days = req.query.days ? parseInt(req.query.days) : 30;
        const patterns = await irrigation_learning_service_1.irrigationLearningService.analyzeFieldPatterns(fieldId);
        const optimalParams = await irrigation_learning_service_1.irrigationLearningService.getOptimalParameters(fieldId);
        res.json({
            fieldId,
            period: `Last ${days} days`,
            patterns,
            optimalParameters: optimalParams,
            insights: generateInsights(patterns, optimalParams)
        });
    }
    catch (error) {
        logger_1.logger.error({ error, fieldId: req.params.fieldId }, 'Failed to get analytics');
        res.status(500).json({ error: 'Failed to get analytics' });
    }
});
router.post('/fields/:fieldId/irrigation/predict', [
    (0, express_validator_1.param)('fieldId').isUUID().withMessage('Invalid field ID'),
    (0, express_validator_1.body)('initialLevel').isFloat({ min: 0, max: 20 }).withMessage('Invalid initial level'),
    (0, express_validator_1.body)('targetLevel').isFloat({ min: 1, max: 20 }).withMessage('Invalid target level'),
    (0, express_validator_1.body)('temperature').optional().isFloat({ min: 0, max: 50 }).withMessage('Invalid temperature'),
    (0, express_validator_1.body)('humidity').optional().isFloat({ min: 0, max: 100 }).withMessage('Invalid humidity')
], async (req, res) => {
    try {
        const errors = (0, express_validator_1.validationResult)(req);
        if (!errors.isEmpty()) {
            return res.status(400).json({ errors: errors.array() });
        }
        const { fieldId } = req.params;
        const prediction = await irrigation_learning_service_1.irrigationLearningService.predictIrrigationPerformance(fieldId, {
            initialLevel: req.body.initialLevel,
            targetLevel: req.body.targetLevel,
            soilType: req.body.soilType || 'loam',
            temperature: req.body.temperature || 28,
            humidity: req.body.humidity || 70,
            lastIrrigationDays: req.body.lastIrrigationDays || 7,
            concurrentIrrigations: req.body.concurrentIrrigations || 0,
            season: req.body.season || getCurrentSeason()
        });
        res.json(prediction);
    }
    catch (error) {
        logger_1.logger.error({ error, fieldId: req.params.fieldId }, 'Failed to predict performance');
        res.status(500).json({ error: 'Failed to predict performance' });
    }
});
router.get('/irrigation/active', [
    (0, express_validator_1.query)('limit').optional().isInt({ min: 1, max: 100 }).withMessage('Limit must be between 1-100'),
    (0, express_validator_1.query)('offset').optional().isInt({ min: 0 }).withMessage('Invalid offset')
], async (req, res) => {
    try {
        const limit = req.query.limit ? parseInt(req.query.limit) : 20;
        const offset = req.query.offset ? parseInt(req.query.offset) : 0;
        res.json({
            active: [],
            total: 0,
            limit,
            offset
        });
    }
    catch (error) {
        logger_1.logger.error({ error }, 'Failed to get active irrigations');
        res.status(500).json({ error: 'Failed to get active irrigations' });
    }
});
function generateInsights(patterns, optimalParams) {
    const insights = [];
    patterns.forEach(pattern => {
        if (pattern.pattern === 'high_flow_variability' && pattern.impact === 'negative') {
            insights.push('High flow rate variability detected - consider maintenance');
        }
        if (pattern.pattern === 'improving_efficiency' && pattern.impact === 'positive') {
            insights.push('Irrigation efficiency has improved recently');
        }
        if (pattern.pattern === 'frequent_anomalies' && pattern.frequency > 10) {
            insights.push('Frequent anomalies detected - system review recommended');
        }
    });
    if (optimalParams.sensorCheckInterval < 300) {
        insights.push('Fast sensor check interval recommended due to quick irrigation times');
    }
    if (optimalParams.toleranceCm < 1.0) {
        insights.push('Tight tolerance recommended due to past anomalies');
    }
    return insights;
}
function getCurrentSeason() {
    const month = new Date().getMonth();
    if (month >= 10 || month <= 1)
        return 'dry';
    if (month >= 5 && month <= 9)
        return 'wet';
    return 'normal';
}
exports.default = router;
//# sourceMappingURL=irrigation-control.routes.js.map