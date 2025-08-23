"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.AlertService = void 0;
const uuid_1 = require("uuid");
const axios_1 = __importDefault(require("axios"));
const config_1 = require("../config");
const logger_1 = require("../utils/logger");
const moisture_model_1 = require("../models/moisture.model");
class AlertService {
    constructor(cacheService) {
        this.alertCooldowns = new Map();
        this.cacheService = cacheService;
    }
    async checkAlerts(reading) {
        const alerts = [];
        // Check low moisture
        if (reading.moistureSurfacePct < config_1.config.alerts.criticalLowMoistureThreshold) {
            const alert = await this.createAlert(reading.sensorId, moisture_model_1.MoistureAlertType.CRITICAL_LOW_MOISTURE, moisture_model_1.AlertSeverity.CRITICAL, reading.moistureSurfacePct, config_1.config.alerts.criticalLowMoistureThreshold, `Critical low surface moisture: ${reading.moistureSurfacePct}%`);
            if (alert)
                alerts.push(alert);
        }
        else if (reading.moistureSurfacePct < config_1.config.alerts.lowMoistureThreshold) {
            const alert = await this.createAlert(reading.sensorId, moisture_model_1.MoistureAlertType.LOW_MOISTURE, moisture_model_1.AlertSeverity.WARNING, reading.moistureSurfacePct, config_1.config.alerts.lowMoistureThreshold, `Low surface moisture: ${reading.moistureSurfacePct}%`);
            if (alert)
                alerts.push(alert);
        }
        // Check high moisture
        if (reading.moistureSurfacePct > config_1.config.alerts.highMoistureThreshold) {
            const alert = await this.createAlert(reading.sensorId, moisture_model_1.MoistureAlertType.HIGH_MOISTURE, moisture_model_1.AlertSeverity.WARNING, reading.moistureSurfacePct, config_1.config.alerts.highMoistureThreshold, `High surface moisture: ${reading.moistureSurfacePct}%`);
            if (alert)
                alerts.push(alert);
        }
        // Check flood status
        if (config_1.config.alerts.floodDetectionEnabled && reading.floodStatus) {
            const alert = await this.createAlert(reading.sensorId, moisture_model_1.MoistureAlertType.FLOOD_DETECTED, moisture_model_1.AlertSeverity.CRITICAL, 1, 0, 'Flood detected by sensor');
            if (alert)
                alerts.push(alert);
        }
        // Check battery voltage if available
        if (reading.voltage && reading.voltage < 3.3) {
            const alert = await this.createAlert(reading.sensorId, moisture_model_1.MoistureAlertType.BATTERY_LOW, moisture_model_1.AlertSeverity.WARNING, reading.voltage, 3.3, `Low battery voltage: ${reading.voltage}V`);
            if (alert)
                alerts.push(alert);
        }
        return alerts;
    }
    async checkSensorOffline(sensorId, lastSeen) {
        const hoursSinceLastSeen = (Date.now() - lastSeen.getTime()) / (1000 * 60 * 60);
        if (hoursSinceLastSeen > 2) {
            return this.createAlert(sensorId, moisture_model_1.MoistureAlertType.SENSOR_OFFLINE, moisture_model_1.AlertSeverity.WARNING, hoursSinceLastSeen, 2, `Sensor offline for ${hoursSinceLastSeen.toFixed(1)} hours`);
        }
        return null;
    }
    async createAlert(sensorId, type, severity, value, threshold, message) {
        // Check cooldown
        const cooldownKey = `${sensorId}:${type}`;
        const lastAlert = this.alertCooldowns.get(cooldownKey);
        if (lastAlert) {
            const minutesSinceLastAlert = (Date.now() - lastAlert.getTime()) / (1000 * 60);
            if (minutesSinceLastAlert < config_1.config.alerts.cooldownMinutes) {
                return null;
            }
        }
        const alert = {
            id: (0, uuid_1.v4)(),
            sensorId,
            type,
            severity,
            value,
            threshold,
            message,
            timestamp: new Date(),
            acknowledged: false,
        };
        // Store alert in cache
        await this.cacheService.set(`alert:${alert.id}`, alert, 86400 // 24 hours
        );
        // Update cooldown
        this.alertCooldowns.set(cooldownKey, new Date());
        // Send to notification service if configured
        if (config_1.config.services.notificationUrl) {
            this.sendNotification(alert).catch(err => {
                logger_1.logger.error({ err, alert }, 'Failed to send notification');
            });
        }
        // Send to alert management service if configured
        if (config_1.config.services.alertUrl) {
            this.sendToAlertService(alert).catch(err => {
                logger_1.logger.error({ err, alert }, 'Failed to send to alert service');
            });
        }
        // Publish to Redis for real-time updates
        await this.cacheService.publish('moisture:alerts', alert);
        logger_1.logger.warn({ alert }, 'Alert created');
        return alert;
    }
    async sendNotification(alert) {
        try {
            await axios_1.default.post(`${config_1.config.services.notificationUrl}/api/v1/notifications`, {
                type: 'moisture_alert',
                severity: alert.severity,
                title: `Moisture Alert: ${alert.type}`,
                message: alert.message,
                data: {
                    alertId: alert.id,
                    sensorId: alert.sensorId,
                    value: alert.value,
                    threshold: alert.threshold,
                },
                channels: alert.severity === moisture_model_1.AlertSeverity.CRITICAL
                    ? ['email', 'sms', 'line']
                    : ['email'],
            });
        }
        catch (error) {
            throw new Error(`Failed to send notification: ${error}`);
        }
    }
    async sendToAlertService(alert) {
        try {
            await axios_1.default.post(`${config_1.config.services.alertUrl}/api/v1/alerts`, {
                source: 'moisture-monitoring',
                alert,
            });
        }
        catch (error) {
            throw new Error(`Failed to send to alert service: ${error}`);
        }
    }
    async acknowledgeAlert(alertId, acknowledgedBy) {
        const alert = await this.cacheService.get(`alert:${alertId}`);
        if (!alert) {
            throw new Error('Alert not found');
        }
        alert.acknowledged = true;
        alert.acknowledgedBy = acknowledgedBy;
        alert.acknowledgedAt = new Date();
        await this.cacheService.set(`alert:${alertId}`, alert, 86400);
        logger_1.logger.info({ alertId, acknowledgedBy }, 'Alert acknowledged');
    }
    async getActiveAlerts(sensorId) {
        // In a production system, this would query a database
        // For now, we'll return an empty array
        logger_1.logger.warn('getActiveAlerts not fully implemented - needs database integration');
        return [];
    }
}
exports.AlertService = AlertService;
//# sourceMappingURL=alert.service.js.map