import { Server } from 'socket.io';
import { Logger } from 'pino';
import { TimescaleRepository } from '../repository/timescale.repository';
import { MqttBroker } from './mqtt-broker';
import { 
  SensorReading, 
  WaterLevelReading, 
  MoistureReading,
  SensorType,
  SensorLocation 
} from '../models/sensor.model';

export interface SensorDataServiceOptions {
  repository: TimescaleRepository;
  mqttBroker: MqttBroker;
  io: Server;
  logger: Logger;
}

export class SensorDataService {
  private repository: TimescaleRepository;
  private mqttBroker: MqttBroker;
  private io: Server;
  private logger: Logger;

  constructor(options: SensorDataServiceOptions) {
    this.repository = options.repository;
    this.mqttBroker = options.mqttBroker;
    this.io = options.io;
    this.logger = options.logger;
  }

  async processSensorData(data: any): Promise<void> {
    try {
      const sensorType = this.detectSensorType(data);
      
      // Special handling for moisture sensors with sensor array
      if (sensorType === SensorType.MOISTURE && data.gateway_id && data.sensor && Array.isArray(data.sensor)) {
        // Process the gateway data once (for the array format)
        const gatewayId = data.gateway_id;
        const location = this.extractLocation(data, sensorType);
        
        // Don't create a gateway-level reading for array data
        // Just process moisture data (this handles the sensor array properly)
        await this.processMoistureData(data, gatewayId, location);
        
        this.logger.info({
          gatewayId,
          sensorCount: data.sensor.length,
          sensorType
        }, 'Processed moisture sensor array');
        
        return; // Exit early for array processing
      }
      
      // Standard processing for non-array sensors
      const sensorId = this.extractSensorId(data, sensorType);
      const location = this.extractLocation(data, sensorType);
      
      // Create sensor reading
      const reading: SensorReading = {
        sensorId,
        sensorType,
        timestamp: new Date(),
        location,
        data,
        metadata: this.extractMetadata(data, sensorType),
        qualityScore: this.calculateQualityScore(data, sensorType)
      };

      // IMPORTANT: Update sensor registry FIRST to ensure sensor exists
      // This will create the sensor if it doesn't exist (ON CONFLICT)
      await this.repository.updateSensorRegistry({
        sensorId,
        sensorType,
        lastSeen: new Date(),
        currentLocation: location,
        metadata: reading.metadata
      });

      // Now save the reading (foreign key constraint will be satisfied)
      await this.repository.saveSensorReading(reading);

      // Publish to MQTT topics
      this.publishToMqtt(reading);

      // Emit to WebSocket clients
      this.emitToWebSocket(reading);

      // Process specific sensor types
      switch (sensorType) {
        case SensorType.WATER_LEVEL:
          await this.processWaterLevelData(data, sensorId, location);
          break;
        case SensorType.MOISTURE:
          await this.processMoistureData(data, sensorId, location);
          break;
      }

      this.logger.info({
        sensorId,
        sensorType,
        location
      }, 'Processed sensor data');

    } catch (error) {
      this.logger.error({ error, data }, 'Failed to process sensor data');
      throw error;
    }
  }

  private detectSensorType(data: any): SensorType {
    if (data.deviceID && data.level !== undefined) {
      return SensorType.WATER_LEVEL;
    }
    if (data.gateway_id && data.sensor) {
      return SensorType.MOISTURE;
    }
    // Support alternative moisture format
    if (data.sensor_id && data.humid_hi !== undefined && data.humid_low !== undefined) {
      return SensorType.MOISTURE;
    }
    return SensorType.UNKNOWN;
  }

  private extractSensorId(data: any, sensorType: SensorType): string {
    switch (sensorType) {
      case SensorType.WATER_LEVEL:
        return data.deviceID;
      case SensorType.MOISTURE:
        // Handle different moisture data formats
        if (data.gateway_id && data.sensor_id) {
          // Direct format with both IDs
          return `${data.gateway_id}-${data.sensor_id}`;
        } else if (data.gateway_id && data.sensor && Array.isArray(data.sensor)) {
          // Array format - this shouldn't normally be called due to special handling
          return `${data.gateway_id}-array`;
        } else if (data.sensor_id) {
          // Fallback to just sensor_id if no gateway
          return data.sensor_id;
        }
        return 'unknown-moisture';
      default:
        return 'unknown';
    }
  }

  private extractLocation(data: any, sensorType: SensorType): SensorLocation | undefined {
    switch (sensorType) {
      case SensorType.WATER_LEVEL:
        return {
          lat: data.latitude,
          lng: data.longitude
        };
      case SensorType.MOISTURE:
        return {
          lat: parseFloat(data.latitude),
          lng: parseFloat(data.longitude)
        };
      default:
        return undefined;
    }
  }

  private extractMetadata(data: any, sensorType: SensorType): any {
    switch (sensorType) {
      case SensorType.WATER_LEVEL:
        return {
          manufacturer: 'RID-R',
          macAddress: data.macAddress,
          battery: data.voltage / 100,
          rssi: data.RSSI
        };
      case SensorType.MOISTURE:
        return {
          manufacturer: 'M2M',
          gatewayId: data.gateway_id,
          gatewayBattery: data.gw_batt ? parseInt(data.gw_batt) / 100 : undefined,
          msgType: data.msg_type,
          gatewayAmbient: {
            temperature: data.temperature ? parseFloat(data.temperature) : undefined,
            humidity: data.humidity ? parseFloat(data.humidity) : undefined,
            heatIndex: data.heat_index ? parseFloat(data.heat_index) : undefined
          }
        };
      default:
        return {};
    }
  }

  private calculateQualityScore(data: any, sensorType: SensorType): number {
    let score = 1.0;

    switch (sensorType) {
      case SensorType.WATER_LEVEL:
        if (data.level < 0 || data.level > 30) score -= 0.3;
        if (data.voltage < 300 || data.voltage > 500) score -= 0.2;
        if (data.RSSI < -100) score -= 0.1;
        break;
      
      case SensorType.MOISTURE:
        if (!data.humid_hi || data.humid_hi < 0 || data.humid_hi > 100) score -= 0.2;
        if (!data.humid_low || data.humid_low < 0 || data.humid_low > 100) score -= 0.2;
        if (data.sensor_batt && parseInt(data.sensor_batt) < 360) score -= 0.2;
        break;
    }

    return Math.max(0, score);
  }

  private async processWaterLevelData(
    data: any, 
    sensorId: string, 
    location?: SensorLocation
  ): Promise<void> {
    const reading: WaterLevelReading = {
      sensorId,
      timestamp: new Date(data.timestamp || Date.now()),
      location,
      levelCm: data.level,
      voltage: data.voltage / 100,
      rssi: data.RSSI,
      qualityScore: this.calculateQualityScore(data, SensorType.WATER_LEVEL)
    };

    await this.repository.saveWaterLevelReading(reading);

    // Check for alerts
    if (reading.levelCm > 25) {
      this.sendAlert({
        type: 'HIGH_WATER_LEVEL',
        sensorId,
        value: reading.levelCm,
        threshold: 25,
        severity: 'critical'
      });
    } else if (reading.levelCm < 5) {
      this.sendAlert({
        type: 'LOW_WATER_LEVEL',
        sensorId,
        value: reading.levelCm,
        threshold: 5,
        severity: 'warning'
      });
    }
  }

  private async processMoistureData(
    data: any, 
    _sensorId: string, 
    location?: SensorLocation
  ): Promise<void> {
    // Handle new M2M moisture sensor format
    if (data.gateway_id && data.sensor && Array.isArray(data.sensor)) {
      // Update gateway metadata
      const gatewayId = `GW-${data.gateway_id.padStart(5, '0')}`;
      await this.repository.updateSensorRegistry({
        sensorId: gatewayId,
        sensorType: SensorType.GATEWAY,
        lastSeen: new Date(),
        currentLocation: location,
        metadata: {
          msgType: data.msg_type,
          temperature: parseFloat(data.temperature),
          humidity: parseFloat(data.humidity),
          heatIndex: parseFloat(data.heat_index),
          battery: parseInt(data.gw_batt) / 100
        }
      });

      // Process each sensor in the array
      for (const sensor of data.sensor) {
        const moistureSensorId = `MS-${data.gateway_id.padStart(5, '0')}-${sensor.sensor_id.padStart(5, '0')}`;
        
        // Parse date/time - handle both formats
        let timestamp: Date;
        if (sensor.date && sensor.time) {
          // Sensor has its own timestamp
          timestamp = this.parseThailandDateTime(sensor.date, sensor.time);
        } else if (data.date && data.time) {
          // Use gateway timestamp
          timestamp = this.parseThailandDateTime(data.date, data.time);
        } else {
          timestamp = new Date();
        }

        // First ensure the moisture sensor is registered
        await this.repository.updateSensorRegistry({
          sensorId: moistureSensorId,
          sensorType: SensorType.MOISTURE,
          lastSeen: timestamp,
          currentLocation: location,
          metadata: {
            gatewayId: gatewayId,
            sensorNumber: sensor.sensor_id,
            manufacturer: 'M2M',
            floodCapable: true
          }
        });

        const reading: MoistureReading = {
          sensorId: moistureSensorId,
          timestamp,
          location,
          moistureSurfacePct: parseFloat(sensor.humid_hi),
          moistureDeepPct: parseFloat(sensor.humid_low),
          tempSurfaceC: parseFloat(sensor.temp_hi),
          tempDeepC: parseFloat(sensor.temp_low),
          ambientHumidityPct: parseFloat(sensor.amb_humid),
          ambientTempC: parseFloat(sensor.amb_temp),
          floodStatus: sensor.flood === 'yes',
          voltage: parseInt(sensor.sensor_batt) / 100,
          qualityScore: this.calculateQualityScore(sensor, SensorType.MOISTURE)
        };

        await this.repository.saveMoistureReading(reading);

        // Check for alerts
        if (reading.moistureSurfacePct < 20) {
          this.sendAlert({
            type: 'LOW_MOISTURE',
            sensorId: moistureSensorId,
            value: reading.moistureSurfacePct,
            threshold: 20,
            severity: 'warning'
          });
        }
        
        if (reading.floodStatus) {
          this.sendAlert({
            type: 'FLOOD_DETECTED',
            sensorId: moistureSensorId,
            value: 1,
            threshold: 0,
            severity: 'critical'
          });
        }
      }
    }
  }

  private publishToMqtt(reading: SensorReading): void {
    const baseTopic = `sensors/${reading.sensorType}`;
    
    // Publish to specific topics
    this.mqttBroker.publish(`${baseTopic}/${reading.sensorId}/data`, {
      timestamp: reading.timestamp,
      data: reading.data,
      qualityScore: reading.qualityScore
    });

    // Publish location updates if changed
    if (reading.location) {
      this.mqttBroker.publish(`${baseTopic}/${reading.sensorId}/location`, {
        timestamp: reading.timestamp,
        location: reading.location
      });
    }
  }

  private emitToWebSocket(reading: SensorReading): void {
    // Emit to specific rooms
    this.io.to(`sensor:${reading.sensorId}`).emit('sensorData', reading);
    this.io.to(`sensorType:${reading.sensorType}`).emit('sensorData', reading);
    
    // Emit to general room
    this.io.emit('sensorData', {
      sensorId: reading.sensorId,
      sensorType: reading.sensorType,
      timestamp: reading.timestamp,
      data: reading.data
    });
  }

  private sendAlert(alert: any): void {
    this.logger.warn({ alert }, 'Sensor alert triggered');
    
    // Publish alert to MQTT
    this.mqttBroker.publish(`alerts/${alert.severity}/${alert.type}`, alert);
    
    // Emit alert to WebSocket
    this.io.emit('alert', alert);
    
    // TODO: Send to notification service
  }

  async getSensorData(
    sensorId: string, 
    startTime: Date, 
    endTime: Date,
    aggregation?: string
  ): Promise<any[]> {
    return this.repository.getSensorReadings(sensorId, startTime, endTime, aggregation);
  }

  async getActiveSensors(): Promise<any[]> {
    return this.repository.getActiveSensors();
  }

  async getSensorsByLocation(
    lat: number, 
    lng: number, 
    radiusKm: number
  ): Promise<any[]> {
    return this.repository.getSensorsByLocation(lat, lng, radiusKm);
  }

  private parseThailandDateTime(date: string, time: string): Date {
    // date format: "2025/05/05", time format: "10:30:00" (UTC)
    const [year, month, day] = date.split('/').map(Number);
    const [hour, minute, second] = time.split(':').map(Number);
    
    // Create UTC date
    const utcDate = new Date(Date.UTC(year, month - 1, day, hour, minute, second));
    
    // Note: The sensor sends UTC time, so no timezone adjustment needed
    return utcDate;
  }
}