import { CacheService } from '../services/cache.service';
import { AlertService } from '../services/alert.service';
import { MqttService } from '../services/mqtt.service';
import { WebSocketService } from '../services/websocket.service';
import { logger } from '../utils/logger';
import { MoistureReading } from '../models/moisture.model';

export class DataProcessor {
  constructor(
    private cacheService: CacheService,
    private alertService: AlertService,
    private mqttService: MqttService,
    private websocketService: WebSocketService
  ) {}

  async start(): Promise<void> {
    // Subscribe to moisture data from sensor ingestion service
    await this.cacheService.subscribe('sensor:moisture:data', async (data: any) => {
      try {
        await this.processMoistureData(data);
      } catch (error) {
        logger.error({ error, data }, 'Failed to process moisture data');
      }
    });
    
    // Subscribe to MQTT data
    this.mqttService.subscribeSensorData(async (data: any) => {
      try {
        if (data.sensorType === 'moisture') {
          await this.processMoistureData(data);
        }
      } catch (error) {
        logger.error({ error, data }, 'Failed to process MQTT moisture data');
      }
    });
    
    logger.info('Data processor started');
  }

  private async processMoistureData(data: any): Promise<void> {
    // Transform data to MoistureReading format
    const reading: MoistureReading = this.transformToMoistureReading(data);
    
    // Check for alerts
    const alerts = await this.alertService.checkAlerts(reading);
    
    // Publish to MQTT
    this.mqttService.publishMoistureReading(reading);
    
    // Emit via WebSocket
    this.websocketService.emitMoistureReading(reading);
    
    // Process alerts
    for (const alert of alerts) {
      this.mqttService.publishMoistureAlert(alert);
      this.websocketService.emitMoistureAlert(alert);
    }
    
    // Update cache with latest reading
    await this.cacheService.set(
      `moisture:latest:${reading.sensorId}`,
      reading,
      300 // 5 minutes
    );
    
    // Invalidate analytics cache for this sensor
    await this.cacheService.invalidateSensorCache(reading.sensorId);
  }

  private transformToMoistureReading(data: any): MoistureReading {
    // Handle different data formats from sensor ingestion
    if (data.gateway_id && data.sensor) {
      // M2M format
      const sensor = Array.isArray(data.sensor) ? data.sensor[0] : data.sensor;
      return {
        sensorId: `${data.gateway_id}-${sensor.sensor_id}`,
        timestamp: new Date(`${data.date} ${data.time}`),
        location: data.latitude && data.longitude ? {
          lat: parseFloat(data.latitude),
          lng: parseFloat(data.longitude),
        } : undefined,
        moistureSurfacePct: parseFloat(sensor.humid_hi),
        moistureDeepPct: parseFloat(sensor.humid_low),
        tempSurfaceC: parseFloat(sensor.temp_hi),
        tempDeepC: parseFloat(sensor.temp_low),
        ambientHumidityPct: parseFloat(sensor.amb_humid),
        ambientTempC: parseFloat(sensor.amb_temp),
        floodStatus: sensor.flood === 'yes',
        voltage: sensor.sensor_batt ? parseFloat(sensor.sensor_batt) / 100 : undefined,
        qualityScore: data.qualityScore,
      };
    } else if (data.sensorId && data.data) {
      // Pre-processed format
      return {
        sensorId: data.sensorId,
        timestamp: new Date(data.timestamp),
        location: data.location,
        moistureSurfacePct: data.data.moistureSurfacePct,
        moistureDeepPct: data.data.moistureDeepPct,
        tempSurfaceC: data.data.tempSurfaceC,
        tempDeepC: data.data.tempDeepC,
        ambientHumidityPct: data.data.ambientHumidityPct,
        ambientTempC: data.data.ambientTempC,
        floodStatus: data.data.floodStatus,
        voltage: data.data.voltage,
        qualityScore: data.qualityScore,
      };
    } else {
      throw new Error('Unknown data format');
    }
  }
}