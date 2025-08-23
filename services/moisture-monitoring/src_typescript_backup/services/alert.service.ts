import { v4 as uuidv4 } from 'uuid';
import axios from 'axios';
import { config } from '../config';
import { logger } from '../utils/logger';
import { CacheService } from './cache.service';
import {
  MoistureReading,
  MoistureAlert,
  MoistureAlertType,
  AlertSeverity,
} from '../models/moisture.model';

export class AlertService {
  private cacheService: CacheService;
  private alertCooldowns: Map<string, Date> = new Map();

  constructor(cacheService: CacheService) {
    this.cacheService = cacheService;
  }

  async checkAlerts(reading: MoistureReading): Promise<MoistureAlert[]> {
    const alerts: MoistureAlert[] = [];
    
    // Check low moisture
    if (reading.moistureSurfacePct < config.alerts.criticalLowMoistureThreshold) {
      const alert = await this.createAlert(
        reading.sensorId,
        MoistureAlertType.CRITICAL_LOW_MOISTURE,
        AlertSeverity.CRITICAL,
        reading.moistureSurfacePct,
        config.alerts.criticalLowMoistureThreshold,
        `Critical low surface moisture: ${reading.moistureSurfacePct}%`
      );
      if (alert) alerts.push(alert);
    } else if (reading.moistureSurfacePct < config.alerts.lowMoistureThreshold) {
      const alert = await this.createAlert(
        reading.sensorId,
        MoistureAlertType.LOW_MOISTURE,
        AlertSeverity.WARNING,
        reading.moistureSurfacePct,
        config.alerts.lowMoistureThreshold,
        `Low surface moisture: ${reading.moistureSurfacePct}%`
      );
      if (alert) alerts.push(alert);
    }
    
    // Check high moisture
    if (reading.moistureSurfacePct > config.alerts.highMoistureThreshold) {
      const alert = await this.createAlert(
        reading.sensorId,
        MoistureAlertType.HIGH_MOISTURE,
        AlertSeverity.WARNING,
        reading.moistureSurfacePct,
        config.alerts.highMoistureThreshold,
        `High surface moisture: ${reading.moistureSurfacePct}%`
      );
      if (alert) alerts.push(alert);
    }
    
    // Check flood status
    if (config.alerts.floodDetectionEnabled && reading.floodStatus) {
      const alert = await this.createAlert(
        reading.sensorId,
        MoistureAlertType.FLOOD_DETECTED,
        AlertSeverity.CRITICAL,
        1,
        0,
        'Flood detected by sensor'
      );
      if (alert) alerts.push(alert);
    }
    
    // Check battery voltage if available
    if (reading.voltage && reading.voltage < 3.3) {
      const alert = await this.createAlert(
        reading.sensorId,
        MoistureAlertType.BATTERY_LOW,
        AlertSeverity.WARNING,
        reading.voltage,
        3.3,
        `Low battery voltage: ${reading.voltage}V`
      );
      if (alert) alerts.push(alert);
    }
    
    return alerts;
  }

  async checkSensorOffline(sensorId: string, lastSeen: Date): Promise<MoistureAlert | null> {
    const hoursSinceLastSeen = (Date.now() - lastSeen.getTime()) / (1000 * 60 * 60);
    
    if (hoursSinceLastSeen > 2) {
      return this.createAlert(
        sensorId,
        MoistureAlertType.SENSOR_OFFLINE,
        AlertSeverity.WARNING,
        hoursSinceLastSeen,
        2,
        `Sensor offline for ${hoursSinceLastSeen.toFixed(1)} hours`
      );
    }
    
    return null;
  }

  private async createAlert(
    sensorId: string,
    type: MoistureAlertType,
    severity: AlertSeverity,
    value: number,
    threshold: number,
    message: string
  ): Promise<MoistureAlert | null> {
    // Check cooldown
    const cooldownKey = `${sensorId}:${type}`;
    const lastAlert = this.alertCooldowns.get(cooldownKey);
    
    if (lastAlert) {
      const minutesSinceLastAlert = (Date.now() - lastAlert.getTime()) / (1000 * 60);
      if (minutesSinceLastAlert < config.alerts.cooldownMinutes) {
        return null;
      }
    }
    
    const alert: MoistureAlert = {
      id: uuidv4(),
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
    await this.cacheService.publish('moisture:alerts', alert);
    
    logger.warn({ alert }, 'Alert created');
    
    return alert;
  }

  private async sendNotification(alert: MoistureAlert): Promise<void> {
    try {
      await axios.post(`${config.services.notificationUrl}/api/v1/notifications`, {
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
        channels: alert.severity === AlertSeverity.CRITICAL 
          ? ['email', 'sms', 'line'] 
          : ['email'],
      });
    } catch (error) {
      throw new Error(`Failed to send notification: ${error}`);
    }
  }

  private async sendToAlertService(alert: MoistureAlert): Promise<void> {
    try {
      await axios.post(`${config.services.alertUrl}/api/v1/alerts`, {
        source: 'moisture-monitoring',
        alert,
      });
    } catch (error) {
      throw new Error(`Failed to send to alert service: ${error}`);
    }
  }

  async acknowledgeAlert(alertId: string, acknowledgedBy: string): Promise<void> {
    const alert = await this.cacheService.get<MoistureAlert>(`alert:${alertId}`);
    
    if (!alert) {
      throw new Error('Alert not found');
    }
    
    alert.acknowledged = true;
    alert.acknowledgedBy = acknowledgedBy;
    alert.acknowledgedAt = new Date();
    
    await this.cacheService.set(`alert:${alertId}`, alert, 86400);
    
    logger.info({ alertId, acknowledgedBy }, 'Alert acknowledged');
  }

  async getActiveAlerts(sensorId?: string): Promise<MoistureAlert[]> {
    // In a production system, this would query a database
    // For now, we'll return an empty array
    logger.warn('getActiveAlerts not fully implemented - needs database integration');
    return [];
  }
}