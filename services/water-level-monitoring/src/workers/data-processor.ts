import { CacheService } from '../services/cache.service';
import { AlertService } from '../services/alert.service';
import { MqttService } from '../services/mqtt.service';
import { WebSocketService } from '../services/websocket.service';
import { GateControlService } from '../services/gate-control.service';
import { logger } from '../utils/logger';
import { WaterLevelReading } from '../models/water-level.model';

export class DataProcessor {
  constructor(
    private cacheService: CacheService,
    private alertService: AlertService,
    private mqttService: MqttService,
    private websocketService: WebSocketService,
    private gateControlService: GateControlService
  ) {}

  async start(): Promise<void> {
    // Subscribe to water level data from sensor ingestion service
    await this.cacheService.subscribe('sensor:water-level:data', async (data: any) => {
      try {
        await this.processWaterLevelData(data);
      } catch (error) {
        logger.error({ error, data }, 'Failed to process water level data');
      }
    });
    
    // Subscribe to MQTT data
    this.mqttService.subscribeSensorData(async (data: any) => {
      try {
        if (data.sensorType === 'water-level') {
          await this.processWaterLevelData(data);
        }
      } catch (error) {
        logger.error({ error, data }, 'Failed to process MQTT water level data');
      }
    });
    
    // Subscribe to gate commands
    this.mqttService.subscribeGateCommands(async (data: any) => {
      try {
        await this.processGateCommand(data);
      } catch (error) {
        logger.error({ error, data }, 'Failed to process gate command');
      }
    });
    
    logger.info('Data processor started');
  }

  private async processWaterLevelData(data: any): Promise<void> {
    // Transform data to WaterLevelReading format
    const reading: WaterLevelReading = this.transformToWaterLevelReading(data);
    
    // Check for alerts
    const alerts = await this.alertService.checkAlerts(reading);
    
    // Publish to MQTT
    this.mqttService.publishWaterLevelReading(reading);
    
    // Emit via WebSocket
    this.websocketService.emitWaterLevelReading(reading);
    
    // Process alerts
    for (const alert of alerts) {
      this.mqttService.publishWaterLevelAlert(alert);
      this.websocketService.emitWaterLevelAlert(alert);
    }
    
    // Update cache with latest reading
    await this.cacheService.set(
      `water-level:latest:${reading.sensorId}`,
      reading,
      300 // 5 minutes
    );
    
    // Invalidate analytics cache for this sensor
    await this.cacheService.invalidateSensorCache(reading.sensorId);
    
    // Check if gate control is needed
    if (data.gateId) {
      const recommendation = await this.gateControlService.generateRecommendation(
        data.gateId,
        reading.sensorId,
        reading
      );
      
      if (recommendation) {
        this.mqttService.publishGateRecommendation(data.gateId, recommendation);
        this.websocketService.emitGateRecommendation(data.gateId, recommendation);
      }
    }
  }

  private transformToWaterLevelReading(data: any): WaterLevelReading {
    // Handle different data formats from sensor ingestion
    if (data.deviceID && data.level !== undefined) {
      // RID-R format
      return {
        sensorId: data.deviceID,
        timestamp: new Date(data.timestamp || Date.now()),
        location: data.latitude && data.longitude ? {
          lat: data.latitude,
          lng: data.longitude,
        } : undefined,
        levelCm: data.level,
        voltage: data.voltage ? data.voltage / 100 : undefined,
        rssi: data.RSSI,
        temperature: data.temperature,
        qualityScore: data.qualityScore,
      };
    } else if (data.sensorId && data.data) {
      // Pre-processed format
      return {
        sensorId: data.sensorId,
        timestamp: new Date(data.timestamp),
        location: data.location,
        levelCm: data.data.levelCm,
        voltage: data.data.voltage,
        rssi: data.data.rssi,
        temperature: data.data.temperature,
        qualityScore: data.qualityScore,
      };
    } else {
      throw new Error('Unknown data format');
    }
  }

  private async processGateCommand(data: any): Promise<void> {
    logger.info({ data }, 'Processing gate command');
    
    // In a real implementation, this would coordinate with the SCADA service
    // For now, just log and emit status
    this.websocketService.emitSystemStatus({
      type: 'gate_command_received',
      gateId: data.gateId,
      command: data.command,
      timestamp: new Date(),
    });
  }
}