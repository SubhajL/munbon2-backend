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
const water_level_model_1 = require("../models/water-level.model");
class AlertService {
    constructor(cacheService, timescaleService) {
        this.alertCooldowns = new Map();
        this.cacheService = cacheService;
        this.timescaleService = timescaleService;
    }
    async checkAlerts(reading) {
        const alerts = [];
        // Check critical low water
        if (reading.levelCm <= config_1.config.alerts.criticalLowWaterThreshold) {
            const alert = await this.createAlert(reading.sensorId, water_level_model_1.WaterLevelAlertType.CRITICAL_LOW_WATER, water_level_model_1.AlertSeverity.CRITICAL, reading.levelCm, config_1.config.alerts.criticalLowWaterThreshold, `Critical low water level: ${reading.levelCm}cm`, { location: reading.location });
            if (alert)
                alerts.push(alert);
        }
        else if (reading.levelCm <= config_1.config.alerts.lowWaterThreshold) {
            const alert = await this.createAlert(reading.sensorId, water_level_model_1.WaterLevelAlertType.LOW_WATER, water_level_model_1.AlertSeverity.WARNING, reading.levelCm, config_1.config.alerts.lowWaterThreshold, `Low water level: ${reading.levelCm}cm`, { location: reading.location });
            if (alert)
                alerts.push(alert);
        }
        // Check critical high water
        if (reading.levelCm >= config_1.config.alerts.criticalHighWaterThreshold) {
            const alert = await this.createAlert(reading.sensorId, water_level_model_1.WaterLevelAlertType.CRITICAL_HIGH_WATER, water_level_model_1.AlertSeverity.CRITICAL, reading.levelCm, config_1.config.alerts.criticalHighWaterThreshold, `Critical high water level: ${reading.levelCm}cm - Flood risk!`, { location: reading.location });
            if (alert)
                alerts.push(alert);
        }
        else if (reading.levelCm >= config_1.config.alerts.highWaterThreshold) {
            const alert = await this.createAlert(reading.sensorId, water_level_model_1.WaterLevelAlertType.HIGH_WATER, water_level_model_1.AlertSeverity.WARNING, reading.levelCm, config_1.config.alerts.highWaterThreshold, `High water level: ${reading.levelCm}cm`, { location: reading.location });
            if (alert)
                alerts.push(alert);
        }
        // Check rapid changes
        const rateOfChange = await this.timescaleService.getRateOfChange(reading.sensorId, 30);
        if (rateOfChange > config_1.config.alerts.rapidChangeThreshold) {
            const alert = await this.createAlert(reading.sensorId, water_level_model_1.WaterLevelAlertType.RAPID_INCREASE, water_level_model_1.AlertSeverity.WARNING, rateOfChange, config_1.config.alerts.rapidChangeThreshold, `Rapid water level increase: ${rateOfChange.toFixed(2)}cm/hour`, {
                location: reading.location,
                rateOfChange,
                previousValue: reading.levelCm - (rateOfChange / 2) // Approximate
            });
            if (alert)
                alerts.push(alert);
        }
        else if (rateOfChange < -config_1.config.alerts.rapidChangeThreshold) {
            const alert = await this.createAlert(reading.sensorId, water_level_model_1.WaterLevelAlertType.RAPID_DECREASE, water_level_model_1.AlertSeverity.WARNING, Math.abs(rateOfChange), config_1.config.alerts.rapidChangeThreshold, `Rapid water level decrease: ${Math.abs(rateOfChange).toFixed(2)}cm/hour`, {
                location: reading.location,
                rateOfChange,
                previousValue: reading.levelCm - (rateOfChange / 2) // Approximate
            });
            if (alert)
                alerts.push(alert);
        }
        // Check battery voltage if available
        if (reading.voltage && reading.voltage < 3.5) {
            const alert = await this.createAlert(reading.sensorId, water_level_model_1.WaterLevelAlertType.BATTERY_LOW, water_level_model_1.AlertSeverity.WARNING, reading.voltage, 3.5, `Low battery voltage: ${reading.voltage}V`, { location: reading.location });
            if (alert)
                alerts.push(alert);
        }
        // Check signal strength if available
        if (reading.rssi && reading.rssi < -90) {
            const alert = await this.createAlert(reading.sensorId, water_level_model_1.WaterLevelAlertType.SIGNAL_WEAK, water_level_model_1.AlertSeverity.INFO, reading.rssi, -90, `Weak signal strength: ${reading.rssi}dBm`, { location: reading.location });
            if (alert)
                alerts.push(alert);
        }
        return alerts;
    }
    async checkSensorOffline(sensorId, lastSeen) {
        const hoursSinceLastSeen = (Date.now() - lastSeen.getTime()) / (1000 * 60 * 60);
        if (hoursSinceLastSeen > 1) {
            return this.createAlert(sensorId, water_level_model_1.WaterLevelAlertType.SENSOR_OFFLINE, water_level_model_1.AlertSeverity.WARNING, hoursSinceLastSeen, 1, `Sensor offline for ${hoursSinceLastSeen.toFixed(1)} hours`);
        }
        return null;
    }
    async createAlert(sensorId, type, severity, value, threshold, message, metadata) {
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
            metadata,
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
        await this.cacheService.publish('water-level:alerts', alert);
        logger_1.logger.warn({ alert }, 'Alert created');
        return alert;
    }
    async sendNotification(alert) {
        try {
            const channels = alert.severity === water_level_model_1.AlertSeverity.CRITICAL
                ? ['email', 'sms', 'line']
                : alert.severity === water_level_model_1.AlertSeverity.WARNING
                    ? ['email', 'line']
                    : ['email'];
            await axios_1.default.post(`${config_1.config.services.notificationUrl}/api/v1/notifications`, {
                type: 'water_level_alert',
                severity: alert.severity,
                title: `Water Level Alert: ${alert.type}`,
                message: alert.message,
                data: {
                    alertId: alert.id,
                    sensorId: alert.sensorId,
                    value: alert.value,
                    threshold: alert.threshold,
                    location: alert.metadata?.location,
                },
                channels,
            });
        }
        catch (error) {
            throw new Error(`Failed to send notification: ${error}`);
        }
    }
    async sendToAlertService(alert) {
        try {
            await axios_1.default.post(`${config_1.config.services.alertUrl}/api/v1/alerts`, {
                source: 'water-level-monitoring',
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