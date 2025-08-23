import { v4 as uuidv4 } from 'uuid';
import axios from 'axios';
import { config } from '../config';
import { logger } from '../utils/logger';
import { CacheService } from './cache.service';
import {
  WeatherReading,
  WeatherAlert,
  WeatherAlertType,
  AlertSeverity,
} from '../models/weather.model';

export class AlertService {
  private cacheService: CacheService;
  private alertCooldowns: Map<string, Date> = new Map();

  constructor(cacheService: CacheService) {
    this.cacheService = cacheService;
  }

  async checkWeatherAlerts(reading: WeatherReading): Promise<WeatherAlert[]> {
    const alerts: WeatherAlert[] = [];
    const location = reading.location || { lat: 0, lng: 0 };
    
    // Check extreme heat
    if (reading.temperature && reading.temperature >= config.alerts.highTempThreshold) {
      const alert = await this.createAlert(
        WeatherAlertType.EXTREME_HEAT,
        AlertSeverity.WARNING,
        'Extreme Heat Warning',
        `Temperature has reached ${reading.temperature}°C`,
        location,
        reading.temperature,
        config.alerts.highTempThreshold
      );
      if (alert) alerts.push(alert);
    }
    
    // Check extreme cold
    if (reading.temperature && reading.temperature <= config.alerts.lowTempThreshold) {
      const alert = await this.createAlert(
        WeatherAlertType.EXTREME_COLD,
        AlertSeverity.WARNING,
        'Cold Weather Alert',
        `Temperature has dropped to ${reading.temperature}°C`,
        location,
        reading.temperature,
        config.alerts.lowTempThreshold
      );
      if (alert) alerts.push(alert);
    }
    
    // Check frost warning
    if (reading.temperature && reading.temperature <= config.alerts.frostWarningTemp) {
      const alert = await this.createAlert(
        WeatherAlertType.FROST_WARNING,
        AlertSeverity.CRITICAL,
        'Frost Warning',
        `Frost risk - Temperature at ${reading.temperature}°C`,
        location,
        reading.temperature,
        config.alerts.frostWarningTemp
      );
      if (alert) alerts.push(alert);
    }
    
    // Check heavy rain
    if (reading.rainfall && reading.rainfall >= config.alerts.heavyRainThreshold) {
      const alert = await this.createAlert(
        WeatherAlertType.HEAVY_RAIN,
        AlertSeverity.WARNING,
        'Heavy Rain Alert',
        `Heavy rainfall of ${reading.rainfall}mm detected`,
        location,
        reading.rainfall,
        config.alerts.heavyRainThreshold
      );
      if (alert) alerts.push(alert);
    }
    
    // Check strong wind
    if (reading.windSpeed && reading.windSpeed >= config.alerts.highWindSpeedThreshold) {
      const alert = await this.createAlert(
        WeatherAlertType.STRONG_WIND,
        AlertSeverity.WARNING,
        'Strong Wind Warning',
        `Wind speed has reached ${reading.windSpeed} km/h`,
        location,
        reading.windSpeed,
        config.alerts.highWindSpeedThreshold
      );
      if (alert) alerts.push(alert);
    }
    
    return alerts;
  }

  async checkForecastAlerts(forecasts: any[]): Promise<WeatherAlert[]> {
    const alerts: WeatherAlert[] = [];
    
    for (const forecast of forecasts) {
      // Check for storm conditions
      if (forecast.conditions === 'thunderstorm' && forecast.confidence > 0.7) {
        const alert = await this.createAlert(
          WeatherAlertType.STORM_WARNING,
          AlertSeverity.CRITICAL,
          'Storm Warning',
          `Thunderstorm expected at ${forecast.forecastTime}`,
          forecast.location,
          undefined,
          undefined,
          {
            validFrom: new Date(),
            validUntil: forecast.forecastTime,
          }
        );
        if (alert) alerts.push(alert);
      }
      
      // Check for drought conditions (no rain for extended period)
      if (forecast.rainfall.amount === 0 && forecast.rainfall.probability < 0.2) {
        // This is simplified - in production, check historical data too
        const alert = await this.createAlert(
          WeatherAlertType.DROUGHT_WARNING,
          AlertSeverity.INFO,
          'Drought Risk',
          'Low rainfall expected in coming days',
          forecast.location,
          forecast.rainfall.amount,
          undefined,
          {
            validFrom: new Date(),
            validUntil: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000),
          }
        );
        if (alert) alerts.push(alert);
      }
    }
    
    return alerts;
  }

  private async createAlert(
    type: WeatherAlertType,
    severity: AlertSeverity,
    title: string,
    message: string,
    location: { lat: number; lng: number },
    value?: number,
    threshold?: number,
    validity?: { validFrom: Date; validUntil: Date }
  ): Promise<WeatherAlert | null> {
    // Check cooldown
    const cooldownKey = `${type}:${location.lat}:${location.lng}`;
    const lastAlert = this.alertCooldowns.get(cooldownKey);
    
    if (lastAlert) {
      const minutesSinceLastAlert = (Date.now() - lastAlert.getTime()) / (1000 * 60);
      if (minutesSinceLastAlert < config.alerts.cooldownMinutes) {
        return null;
      }
    }
    
    const alert: WeatherAlert = {
      id: uuidv4(),
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
    await this.cacheService.set(
      `alert:${alert.id}`,
      alert,
      86400 // 24 hours
    );
    
    // Update cooldown
    this.alertCooldowns.set(cooldownKey, new Date());
    
    // Send to notification service if configured
    if (config.services.notificationUrl) {
      this.sendNotification(alert).catch(err => {
        logger.error({ err, alert }, 'Failed to send notification');
      });
    }
    
    // Send to alert management service if configured
    if (config.services.alertUrl) {
      this.sendToAlertService(alert).catch(err => {
        logger.error({ err, alert }, 'Failed to send to alert service');
      });
    }
    
    // Publish to Redis for real-time updates
    await this.cacheService.publish('weather:alerts', alert);
    
    logger.warn({ alert }, 'Weather alert created');
    
    return alert;
  }

  private async sendNotification(alert: WeatherAlert): Promise<void> {
    try {
      const channels = alert.severity === AlertSeverity.CRITICAL 
        ? ['email', 'sms', 'line'] 
        : alert.severity === AlertSeverity.WARNING
        ? ['email', 'line']
        : ['email'];
        
      await axios.post(`${config.services.notificationUrl}/api/v1/notifications`, {
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
    } catch (error) {
      throw new Error(`Failed to send notification: ${error}`);
    }
  }

  private async sendToAlertService(alert: WeatherAlert): Promise<void> {
    try {
      await axios.post(`${config.services.alertUrl}/api/v1/alerts`, {
        source: 'weather-monitoring',
        alert,
      });
    } catch (error) {
      throw new Error(`Failed to send to alert service: ${error}`);
    }
  }

  async acknowledgeAlert(alertId: string, acknowledgedBy: string): Promise<void> {
    const alert = await this.cacheService.get<WeatherAlert>(`alert:${alertId}`);
    
    if (!alert) {
      throw new Error('Alert not found');
    }
    
    alert.acknowledged = true;
    alert.acknowledgedBy = acknowledgedBy;
    alert.acknowledgedAt = new Date();
    
    await this.cacheService.set(`alert:${alertId}`, alert, 86400);
    
    logger.info({ alertId, acknowledgedBy }, 'Alert acknowledged');
  }

  async getActiveAlerts(location?: { lat: number; lng: number }, radius?: number): Promise<WeatherAlert[]> {
    // In a production system, this would query a database
    // For now, we'll return an empty array
    logger.warn('getActiveAlerts not fully implemented - needs database integration');
    return [];
  }
}