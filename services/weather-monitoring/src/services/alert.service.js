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
const weather_model_1 = require("../models/weather.model");
class AlertService {
    constructor(cacheService) {
        this.alertCooldowns = new Map();
        this.cacheService = cacheService;
    }
    async checkWeatherAlerts(reading) {
        const alerts = [];
        const location = reading.location || { lat: 0, lng: 0 };
        // Check extreme heat
        if (reading.temperature && reading.temperature >= config_1.config.alerts.highTempThreshold) {
            const alert = await this.createAlert(weather_model_1.WeatherAlertType.EXTREME_HEAT, weather_model_1.AlertSeverity.WARNING, 'Extreme Heat Warning', `Temperature has reached ${reading.temperature}°C`, location, reading.temperature, config_1.config.alerts.highTempThreshold);
            if (alert)
                alerts.push(alert);
        }
        // Check extreme cold
        if (reading.temperature && reading.temperature <= config_1.config.alerts.lowTempThreshold) {
            const alert = await this.createAlert(weather_model_1.WeatherAlertType.EXTREME_COLD, weather_model_1.AlertSeverity.WARNING, 'Cold Weather Alert', `Temperature has dropped to ${reading.temperature}°C`, location, reading.temperature, config_1.config.alerts.lowTempThreshold);
            if (alert)
                alerts.push(alert);
        }
        // Check frost warning
        if (reading.temperature && reading.temperature <= config_1.config.alerts.frostWarningTemp) {
            const alert = await this.createAlert(weather_model_1.WeatherAlertType.FROST_WARNING, weather_model_1.AlertSeverity.CRITICAL, 'Frost Warning', `Frost risk - Temperature at ${reading.temperature}°C`, location, reading.temperature, config_1.config.alerts.frostWarningTemp);
            if (alert)
                alerts.push(alert);
        }
        // Check heavy rain
        if (reading.rainfall && reading.rainfall >= config_1.config.alerts.heavyRainThreshold) {
            const alert = await this.createAlert(weather_model_1.WeatherAlertType.HEAVY_RAIN, weather_model_1.AlertSeverity.WARNING, 'Heavy Rain Alert', `Heavy rainfall of ${reading.rainfall}mm detected`, location, reading.rainfall, config_1.config.alerts.heavyRainThreshold);
            if (alert)
                alerts.push(alert);
        }
        // Check strong wind
        if (reading.windSpeed && reading.windSpeed >= config_1.config.alerts.highWindSpeedThreshold) {
            const alert = await this.createAlert(weather_model_1.WeatherAlertType.STRONG_WIND, weather_model_1.AlertSeverity.WARNING, 'Strong Wind Warning', `Wind speed has reached ${reading.windSpeed} km/h`, location, reading.windSpeed, config_1.config.alerts.highWindSpeedThreshold);
            if (alert)
                alerts.push(alert);
        }
        return alerts;
    }
    async checkForecastAlerts(forecasts) {
        const alerts = [];
        for (const forecast of forecasts) {
            // Check for storm conditions
            if (forecast.conditions === 'thunderstorm' && forecast.confidence > 0.7) {
                const alert = await this.createAlert(weather_model_1.WeatherAlertType.STORM_WARNING, weather_model_1.AlertSeverity.CRITICAL, 'Storm Warning', `Thunderstorm expected at ${forecast.forecastTime}`, forecast.location, undefined, undefined, {
                    validFrom: new Date(),
                    validUntil: forecast.forecastTime,
                });
                if (alert)
                    alerts.push(alert);
            }
            // Check for drought conditions (no rain for extended period)
            if (forecast.rainfall.amount === 0 && forecast.rainfall.probability < 0.2) {
                // This is simplified - in production, check historical data too
                const alert = await this.createAlert(weather_model_1.WeatherAlertType.DROUGHT_WARNING, weather_model_1.AlertSeverity.INFO, 'Drought Risk', 'Low rainfall expected in coming days', forecast.location, forecast.rainfall.amount, undefined, {
                    validFrom: new Date(),
                    validUntil: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000),
                });
                if (alert)
                    alerts.push(alert);
            }
        }
        return alerts;
    }
    async createAlert(type, severity, title, message, location, value, threshold, validity) {
        // Check cooldown
        const cooldownKey = `${type}:${location.lat}:${location.lng}`;
        const lastAlert = this.alertCooldowns.get(cooldownKey);
        if (lastAlert) {
            const minutesSinceLastAlert = (Date.now() - lastAlert.getTime()) / (1000 * 60);
            if (minutesSinceLastAlert < config_1.config.alerts.cooldownMinutes) {
                return null;
            }
        }
        const alert = {
            id: (0, uuid_1.v4)(),
            type,
            severity,
            title,
            message,
            affectedArea: {
                type: 'point',
                coordinates: [location.lng, location.lat],
            },
            validFrom: validity?.validFrom || new Date(),
            validUntil: validity?.validUntil || new Date(Date.now() + 24 * 60 * 60 * 1000),
            value,
            threshold,
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
        await this.cacheService.publish('weather:alerts', alert);
        logger_1.logger.warn({ alert }, 'Weather alert created');
        return alert;
    }
    async sendNotification(alert) {
        try {
            const channels = alert.severity === weather_model_1.AlertSeverity.CRITICAL
                ? ['email', 'sms', 'line']
                : alert.severity === weather_model_1.AlertSeverity.WARNING
                    ? ['email', 'line']
                    : ['email'];
            await axios_1.default.post(`${config_1.config.services.notificationUrl}/api/v1/notifications`, {
                type: 'weather_alert',
                severity: alert.severity,
                title: alert.title,
                message: alert.message,
                data: {
                    alertId: alert.id,
                    alertType: alert.type,
                    location: alert.affectedArea,
                    value: alert.value,
                    threshold: alert.threshold,
                    validUntil: alert.validUntil,
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
                source: 'weather-monitoring',
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
    async getActiveAlerts(location, radius) {
        // In a production system, this would query a database
        // For now, we'll return an empty array
        logger_1.logger.warn('getActiveAlerts not fully implemented - needs database integration');
        return [];
    }
}
exports.AlertService = AlertService;
//# sourceMappingURL=alert.service.js.map