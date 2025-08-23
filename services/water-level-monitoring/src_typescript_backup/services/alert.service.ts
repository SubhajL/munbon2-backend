import { v4 as uuidv4 } from 'uuid';
import axios from 'axios';
import { config } from '../config';
import { logger } from '../utils/logger';
import { CacheService } from './cache.service';
import { TimescaleService } from './timescale.service';
import {
  WaterLevelReading,
  WaterLevelAlert,
  WaterLevelAlertType,
  AlertSeverity,
} from '../models/water-level.model';

export class AlertService {
  private cacheService: CacheService;
  private timescaleService: TimescaleService;
  private alertCooldowns: Map<string, Date> = new Map();

  constructor(cacheService: CacheService, timescaleService: TimescaleService) {
    this.cacheService = cacheService;
    this.timescaleService = timescaleService;
  }

  async checkAlerts(reading: WaterLevelReading): Promise<WaterLevelAlert[]> {
    const alerts: WaterLevelAlert[] = [];
    
    // Check critical low water
    if (reading.levelCm <= config.alerts.criticalLowWaterThreshold) {
      const alert = await this.createAlert(
        reading.sensorId,
        WaterLevelAlertType.CRITICAL_LOW_WATER,
        AlertSeverity.CRITICAL,
        reading.levelCm,
        config.alerts.criticalLowWaterThreshold,
        `Critical low water level: ${reading.levelCm}cm`,
        { location: reading.location }
      );
      if (alert) alerts.push(alert);
    } else if (reading.levelCm <= config.alerts.lowWaterThreshold) {
      const alert = await this.createAlert(
        reading.sensorId,
        WaterLevelAlertType.LOW_WATER,
        AlertSeverity.WARNING,
        reading.levelCm,
        config.alerts.lowWaterThreshold,
        `Low water level: ${reading.levelCm}cm`,
        { location: reading.location }
      );
      if (alert) alerts.push(alert);
    }
    
    // Check critical high water
    if (reading.levelCm >= config.alerts.criticalHighWaterThreshold) {
      const alert = await this.createAlert(
        reading.sensorId,
        WaterLevelAlertType.CRITICAL_HIGH_WATER,
        AlertSeverity.CRITICAL,
        reading.levelCm,
        config.alerts.criticalHighWaterThreshold,
        `Critical high water level: ${reading.levelCm}cm - Flood risk!`,
        { location: reading.location }
      );
      if (alert) alerts.push(alert);
    } else if (reading.levelCm >= config.alerts.highWaterThreshold) {
      const alert = await this.createAlert(
        reading.sensorId,
        WaterLevelAlertType.HIGH_WATER,
        AlertSeverity.WARNING,
        reading.levelCm,
        config.alerts.highWaterThreshold,
        `High water level: ${reading.levelCm}cm`,
        { location: reading.location }
      );
      if (alert) alerts.push(alert);
    }
    
    // Check rapid changes
    const rateOfChange = await this.timescaleService.getRateOfChange(reading.sensorId, 30);
    
    if (rateOfChange > config.alerts.rapidChangeThreshold) {
      const alert = await this.createAlert(
        reading.sensorId,
        WaterLevelAlertType.RAPID_INCREASE,
        AlertSeverity.WARNING,
        rateOfChange,
        config.alerts.rapidChangeThreshold,
        `Rapid water level increase: ${rateOfChange.toFixed(2)}cm/hour`,
        { 
          location: reading.location,
          rateOfChange,
          previousValue: reading.levelCm - (rateOfChange / 2) // Approximate
        }
      );
      if (alert) alerts.push(alert);
    } else if (rateOfChange < -config.alerts.rapidChangeThreshold) {
      const alert = await this.createAlert(
        reading.sensorId,
        WaterLevelAlertType.RAPID_DECREASE,
        AlertSeverity.WARNING,
        Math.abs(rateOfChange),
        config.alerts.rapidChangeThreshold,
        `Rapid water level decrease: ${Math.abs(rateOfChange).toFixed(2)}cm/hour`,
        { 
          location: reading.location,
          rateOfChange,
          previousValue: reading.levelCm - (rateOfChange / 2) // Approximate
        }
      );
      if (alert) alerts.push(alert);
    }
    
    // Check battery voltage if available
    if (reading.voltage && reading.voltage < 3.5) {
      const alert = await this.createAlert(
        reading.sensorId,
        WaterLevelAlertType.BATTERY_LOW,
        AlertSeverity.WARNING,
        reading.voltage,
        3.5,
        `Low battery voltage: ${reading.voltage}V`,
        { location: reading.location }
      );
      if (alert) alerts.push(alert);
    }
    
    // Check signal strength if available
    if (reading.rssi && reading.rssi < -90) {
      const alert = await this.createAlert(
        reading.sensorId,
        WaterLevelAlertType.SIGNAL_WEAK,
        AlertSeverity.INFO,
        reading.rssi,
        -90,
        `Weak signal strength: ${reading.rssi}dBm`,
        { location: reading.location }
      );
      if (alert) alerts.push(alert);
    }
    
    return alerts;
  }

  async checkSensorOffline(sensorId: string, lastSeen: Date): Promise<WaterLevelAlert | null> {
    const hoursSinceLastSeen = (Date.now() - lastSeen.getTime()) / (1000 * 60 * 60);
    
    if (hoursSinceLastSeen > 1) {
      return this.createAlert(
        sensorId,
        WaterLevelAlertType.SENSOR_OFFLINE,
        AlertSeverity.WARNING,
        hoursSinceLastSeen,
        1,
        `Sensor offline for ${hoursSinceLastSeen.toFixed(1)} hours`
      );
    }
    
    return null;
  }

  private async createAlert(
    sensorId: string,
    type: WaterLevelAlertType,
    severity: AlertSeverity,
    value: number,
    threshold: number,
    message: string,
    metadata?: any
  ): Promise<WaterLevelAlert | null> {
    // Check cooldown
    const cooldownKey = `${sensorId}:${type}`;
    const lastAlert = this.alertCooldowns.get(cooldownKey);
    
    if (lastAlert) {
      const minutesSinceLastAlert = (Date.now() - lastAlert.getTime()) / (1000 * 60);
      if (minutesSinceLastAlert < config.alerts.cooldownMinutes) {
        return null;
      }
    }
    
    const alert: WaterLevelAlert = {
      id: uuidv4(),
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
    await this.cacheService.publish('water-level:alerts', alert);
    
    logger.warn({ alert }, 'Alert created');
    
    return alert;
  }

  private async sendNotification(alert: WaterLevelAlert): Promise<void> {
    try {
      const channels = alert.severity === AlertSeverity.CRITICAL 
        ? ['email', 'sms', 'line'] 
        : alert.severity === AlertSeverity.WARNING
        ? ['email', 'line']
        : ['email'];
        
      await axios.post(`${config.services.notificationUrl}/api/v1/notifications`, {
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
    } catch (error) {
      throw new Error(`Failed to send notification: ${error}`);
    }
  }

  private async sendToAlertService(alert: WaterLevelAlert): Promise<void> {
    try {
      await axios.post(`${config.services.alertUrl}/api/v1/alerts`, {
        source: 'water-level-monitoring',
        alert,
      });
    } catch (error) {
      throw new Error(`Failed to send to alert service: ${error}`);
    }
  }

  async acknowledgeAlert(alertId: string, acknowledgedBy: string): Promise<void> {
    const alert = await this.cacheService.get<WaterLevelAlert>(`alert:${alertId}`);
    
    if (!alert) {
      throw new Error('Alert not found');
    }
    
    alert.acknowledged = true;
    alert.acknowledgedBy = acknowledgedBy;
    alert.acknowledgedAt = new Date();
    
    await this.cacheService.set(`alert:${alertId}`, alert, 86400);
    
    logger.info({ alertId, acknowledgedBy }, 'Alert acknowledged');
  }

  async getActiveAlerts(sensorId?: string): Promise<WaterLevelAlert[]> {
    // In a production system, this would query a database
    // For now, we'll return an empty array
    logger.warn('getActiveAlerts not fully implemented - needs database integration');
    return [];
  }
}