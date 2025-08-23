"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const express_validator_1 = require("express-validator");
const database_1 = require("../config/database");
const logger_1 = require("../utils/logger");
const router = (0, express_1.Router)();
const postgresPool = (0, database_1.getPostgresPool)();
router.get('/monitoring/irrigation/:scheduleId/realtime', [
    (0, express_validator_1.param)('scheduleId').isUUID().withMessage('Invalid schedule ID'),
    (0, express_validator_1.query)('limit').optional().isInt({ min: 1, max: 1000 }).withMessage('Limit must be between 1-1000')
], async (req, res) => {
    try {
        const errors = (0, express_validator_1.validationResult)(req);
        if (!errors.isEmpty()) {
            return res.status(400).json({ errors: errors.array() });
        }
        const { scheduleId } = req.params;
        const limit = req.query.limit ? parseInt(req.query.limit) : 100;
        const result = await postgresPool.query(`
        SELECT 
          timestamp,
          water_level_cm,
          flow_rate_cm_per_min,
          sensor_id,
          sensor_reliability
        FROM awd.irrigation_monitoring
        WHERE schedule_id = $1
        ORDER BY timestamp DESC
        LIMIT $2
      `, [scheduleId, limit]);
        res.json({
            scheduleId,
            dataPoints: result.rows.reverse(),
            count: result.rows.length
        });
    }
    catch (error) {
        logger_1.logger.error({ error, scheduleId: req.params.scheduleId }, 'Failed to get realtime data');
        res.status(500).json({ error: 'Failed to get monitoring data' });
    }
});
router.get('/monitoring/fields/:fieldId/performance', [
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
        const performanceResult = await postgresPool.query(`
        SELECT 
          COUNT(*) as total_irrigations,
          AVG(efficiency_score) as avg_efficiency,
          AVG(total_duration_minutes) as avg_duration_minutes,
          AVG(water_volume_liters) as avg_water_volume,
          SUM(water_volume_liters) as total_water_used,
          AVG(water_saved_percent) as avg_water_saved,
          SUM(CASE WHEN efficiency_score > 0.8 THEN 1 ELSE 0 END) as high_efficiency_count,
          SUM(anomalies_detected) as total_anomalies
        FROM awd.irrigation_performance
        WHERE field_id = $1
          AND start_time > NOW() - INTERVAL '%s days'
      `, [fieldId, days]);
        const anomalyResult = await postgresPool.query(`
        SELECT 
          anomaly_type,
          severity,
          COUNT(*) as count
        FROM awd.irrigation_anomalies
        WHERE field_id = $1
          AND detected_at > NOW() - INTERVAL '%s days'
        GROUP BY anomaly_type, severity
        ORDER BY count DESC
      `, [fieldId, days]);
        const trendResult = await postgresPool.query(`
        SELECT 
          DATE_TRUNC('day', start_time) as date,
          AVG(efficiency_score) as efficiency,
          AVG(total_duration_minutes) as duration,
          COUNT(*) as irrigations
        FROM awd.irrigation_performance
        WHERE field_id = $1
          AND start_time > NOW() - INTERVAL '%s days'
        GROUP BY DATE_TRUNC('day', start_time)
        ORDER BY date
      `, [fieldId, days]);
        const performance = performanceResult.rows[0];
        res.json({
            fieldId,
            period: `${days} days`,
            summary: {
                totalIrrigations: parseInt(performance.total_irrigations),
                avgEfficiency: parseFloat(performance.avg_efficiency || '0').toFixed(2),
                avgDurationHours: (parseFloat(performance.avg_duration_minutes || '0') / 60).toFixed(1),
                avgWaterVolume: Math.round(parseFloat(performance.avg_water_volume || '0')),
                totalWaterUsed: Math.round(parseFloat(performance.total_water_used || '0')),
                avgWaterSaved: parseFloat(performance.avg_water_saved || '0').toFixed(1),
                highEfficiencyRate: (parseInt(performance.high_efficiency_count) / parseInt(performance.total_irrigations) * 100).toFixed(1),
                totalAnomalies: parseInt(performance.total_anomalies)
            },
            anomalies: anomalyResult.rows,
            trend: trendResult.rows.map(row => ({
                date: row.date,
                efficiency: parseFloat(row.efficiency).toFixed(2),
                avgDurationHours: (parseFloat(row.duration) / 60).toFixed(1),
                count: parseInt(row.irrigations)
            }))
        });
    }
    catch (error) {
        logger_1.logger.error({ error, fieldId: req.params.fieldId }, 'Failed to get performance summary');
        res.status(500).json({ error: 'Failed to get performance summary' });
    }
});
router.get('/monitoring/anomalies', [
    (0, express_validator_1.query)('fieldId').optional().isUUID().withMessage('Invalid field ID'),
    (0, express_validator_1.query)('type').optional().isIn(['low_flow', 'no_rise', 'rapid_drop', 'sensor_failure', 'overflow_risk']),
    (0, express_validator_1.query)('severity').optional().isIn(['warning', 'critical']),
    (0, express_validator_1.query)('resolved').optional().isBoolean(),
    (0, express_validator_1.query)('days').optional().isInt({ min: 1, max: 365 }),
    (0, express_validator_1.query)('limit').optional().isInt({ min: 1, max: 1000 }),
    (0, express_validator_1.query)('offset').optional().isInt({ min: 0 })
], async (req, res) => {
    try {
        const errors = (0, express_validator_1.validationResult)(req);
        if (!errors.isEmpty()) {
            return res.status(400).json({ errors: errors.array() });
        }
        const days = req.query.days ? parseInt(req.query.days) : 7;
        const limit = req.query.limit ? parseInt(req.query.limit) : 50;
        const offset = req.query.offset ? parseInt(req.query.offset) : 0;
        let whereConditions = ['detected_at > NOW() - INTERVAL \'' + days + ' days\''];
        const params = [];
        let paramCount = 0;
        if (req.query.fieldId) {
            whereConditions.push(`field_id = $${++paramCount}`);
            params.push(req.query.fieldId);
        }
        if (req.query.type) {
            whereConditions.push(`anomaly_type = $${++paramCount}`);
            params.push(req.query.type);
        }
        if (req.query.severity) {
            whereConditions.push(`severity = $${++paramCount}`);
            params.push(req.query.severity);
        }
        if (req.query.resolved !== undefined) {
            const resolved = req.query.resolved === 'true';
            whereConditions.push(resolved ? `resolved_at IS NOT NULL` : `resolved_at IS NULL`);
        }
        const countQuery = `
        SELECT COUNT(*) as total
        FROM awd.irrigation_anomalies
        WHERE ${whereConditions.join(' AND ')}
      `;
        const dataQuery = `
        SELECT 
          a.*,
          f.name as field_name,
          s.scheduled_start as irrigation_start
        FROM awd.irrigation_anomalies a
        JOIN awd.awd_fields f ON a.field_id = f.id
        LEFT JOIN awd.irrigation_schedules s ON a.schedule_id = s.id
        WHERE ${whereConditions.join(' AND ')}
        ORDER BY a.detected_at DESC
        LIMIT $${++paramCount} OFFSET $${++paramCount}
      `;
        params.push(limit, offset);
        const [countResult, dataResult] = await Promise.all([
            postgresPool.query(countQuery, params.slice(0, -2)),
            postgresPool.query(dataQuery, params)
        ]);
        res.json({
            anomalies: dataResult.rows,
            pagination: {
                total: parseInt(countResult.rows[0].total),
                limit,
                offset,
                hasMore: offset + limit < parseInt(countResult.rows[0].total)
            },
            filters: {
                days,
                fieldId: req.query.fieldId,
                type: req.query.type,
                severity: req.query.severity,
                resolved: req.query.resolved
            }
        });
    }
    catch (error) {
        logger_1.logger.error({ error }, 'Failed to get anomalies');
        res.status(500).json({ error: 'Failed to get anomalies' });
    }
});
router.get('/monitoring/water-usage', [
    (0, express_validator_1.query)('groupBy').optional().isIn(['field', 'day', 'week', 'month']),
    (0, express_validator_1.query)('days').optional().isInt({ min: 1, max: 365 })
], async (req, res) => {
    try {
        const errors = (0, express_validator_1.validationResult)(req);
        if (!errors.isEmpty()) {
            return res.status(400).json({ errors: errors.array() });
        }
        const groupBy = req.query.groupBy || 'day';
        const days = req.query.days ? parseInt(req.query.days) : 30;
        let query = '';
        switch (groupBy) {
            case 'field':
                query = `
            SELECT 
              f.id as field_id,
              f.name as field_name,
              COUNT(p.id) as irrigation_count,
              SUM(p.water_volume_liters) as total_water,
              AVG(p.water_volume_liters) as avg_water_per_irrigation,
              AVG(p.efficiency_score) as avg_efficiency,
              SUM(p.water_saved_percent * p.water_volume_liters / 100) as water_saved
            FROM awd.awd_fields f
            LEFT JOIN awd.irrigation_performance p ON f.id = p.field_id
              AND p.start_time > NOW() - INTERVAL '${days} days'
            GROUP BY f.id, f.name
            ORDER BY total_water DESC NULLS LAST
          `;
                break;
            case 'week':
                query = `
            SELECT 
              DATE_TRUNC('week', start_time) as period,
              COUNT(*) as irrigation_count,
              SUM(water_volume_liters) as total_water,
              AVG(water_volume_liters) as avg_water,
              AVG(efficiency_score) as avg_efficiency,
              COUNT(DISTINCT field_id) as fields_irrigated
            FROM awd.irrigation_performance
            WHERE start_time > NOW() - INTERVAL '${days} days'
            GROUP BY DATE_TRUNC('week', start_time)
            ORDER BY period
          `;
                break;
            case 'month':
                query = `
            SELECT 
              DATE_TRUNC('month', start_time) as period,
              COUNT(*) as irrigation_count,
              SUM(water_volume_liters) as total_water,
              AVG(water_volume_liters) as avg_water,
              AVG(efficiency_score) as avg_efficiency,
              COUNT(DISTINCT field_id) as fields_irrigated
            FROM awd.irrigation_performance
            WHERE start_time > NOW() - INTERVAL '${days} days'
            GROUP BY DATE_TRUNC('month', start_time)
            ORDER BY period
          `;
                break;
            default:
                query = `
            SELECT 
              DATE_TRUNC('day', start_time) as period,
              COUNT(*) as irrigation_count,
              SUM(water_volume_liters) as total_water,
              AVG(water_volume_liters) as avg_water,
              AVG(efficiency_score) as avg_efficiency,
              COUNT(DISTINCT field_id) as fields_irrigated
            FROM awd.irrigation_performance
            WHERE start_time > NOW() - INTERVAL '${days} days'
            GROUP BY DATE_TRUNC('day', start_time)
            ORDER BY period
          `;
        }
        const result = await postgresPool.query(query);
        const totals = result.rows.reduce((acc, row) => ({
            totalWater: acc.totalWater + parseFloat(row.total_water || '0'),
            totalIrrigations: acc.totalIrrigations + parseInt(row.irrigation_count || '0'),
            avgEfficiency: acc.avgEfficiency + parseFloat(row.avg_efficiency || '0')
        }), { totalWater: 0, totalIrrigations: 0, avgEfficiency: 0 });
        if (result.rows.length > 0) {
            totals.avgEfficiency = totals.avgEfficiency / result.rows.length;
        }
        res.json({
            data: result.rows.map(row => ({
                ...row,
                total_water: Math.round(parseFloat(row.total_water || '0')),
                avg_water: Math.round(parseFloat(row.avg_water || '0')),
                avg_efficiency: parseFloat(row.avg_efficiency || '0').toFixed(2)
            })),
            summary: {
                period: `${days} days`,
                groupBy,
                totalWaterUsed: Math.round(totals.totalWater),
                totalIrrigations: totals.totalIrrigations,
                avgEfficiency: totals.avgEfficiency.toFixed(2)
            }
        });
    }
    catch (error) {
        logger_1.logger.error({ error }, 'Failed to get water usage analytics');
        res.status(500).json({ error: 'Failed to get water usage analytics' });
    }
});
router.get('/monitoring/gates/:gateId/history', [
    (0, express_validator_1.param)('gateId').isString().notEmpty().withMessage('Invalid gate ID'),
    (0, express_validator_1.query)('days').optional().isInt({ min: 1, max: 365 })
], async (req, res) => {
    try {
        const errors = (0, express_validator_1.validationResult)(req);
        if (!errors.isEmpty()) {
            return res.status(400).json({ errors: errors.array() });
        }
        const { gateId } = req.params;
        const days = req.query.days ? parseInt(req.query.days) : 7;
        const result = await postgresPool.query(`
        SELECT 
          g.*,
          f.name as field_name
        FROM awd.gate_control_logs g
        LEFT JOIN awd.awd_fields f ON g.field_id = f.id
        WHERE g.gate_id = $1
          AND g.requested_at > NOW() - INTERVAL '%s days'
        ORDER BY g.requested_at DESC
        LIMIT 100
      `, [gateId, days]);
        const stats = await postgresPool.query(`
        SELECT 
          COUNT(*) as total_operations,
          SUM(CASE WHEN success = true THEN 1 ELSE 0 END) as successful,
          SUM(CASE WHEN success = false THEN 1 ELSE 0 END) as failed,
          AVG(EXTRACT(EPOCH FROM (executed_at - requested_at))) as avg_response_time_seconds
        FROM awd.gate_control_logs
        WHERE gate_id = $1
          AND requested_at > NOW() - INTERVAL '%s days'
      `, [gateId, days]);
        res.json({
            gateId,
            history: result.rows,
            statistics: {
                period: `${days} days`,
                totalOperations: parseInt(stats.rows[0].total_operations),
                successRate: (parseInt(stats.rows[0].successful) / parseInt(stats.rows[0].total_operations) * 100).toFixed(1),
                avgResponseTime: parseFloat(stats.rows[0].avg_response_time_seconds || '0').toFixed(2)
            }
        });
    }
    catch (error) {
        logger_1.logger.error({ error, gateId: req.params.gateId }, 'Failed to get gate history');
        res.status(500).json({ error: 'Failed to get gate history' });
    }
});
exports.default = router;
//# sourceMappingURL=monitoring-dashboard.routes.js.map