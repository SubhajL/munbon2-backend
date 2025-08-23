import mqtt, { MqttClient, IClientOptions } from 'mqtt';
import { config } from '../config';
import { logger } from '../utils/logger';
import { MoistureReading, MoistureAlert } from '../models/moisture.model';

export class MqttService {
  private client: MqttClient;
  private connected: boolean = false;
  private subscriptions: Map<string, (data: any) => void> = new Map();

  constructor() {
    const options: IClientOptions = {
      clientId: config.mqtt.clientId,
      clean: true,
      connectTimeout: 4000,
      reconnectPeriod: config.mqtt.reconnectPeriod,
    };
    
    if (config.mqtt.username) {
      options.username = config.mqtt.username;
      options.password = config.mqtt.password;
    }
    
    this.client = mqtt.connect(config.mqtt.brokerUrl, options);
    
    this.setupEventHandlers();
  }

  private setupEventHandlers(): void {
    this.client.on('connect', () => {
      this.connected = true;
      logger.info('Connected to MQTT broker');
      
      // Resubscribe to topics after reconnection
      this.subscriptions.forEach((_, topic) => {
        this.client.subscribe(topic, (err) => {
          if (err) {
            logger.error({ err, topic }, 'Failed to resubscribe to topic');
          }
        });
      });
    });
    
    this.client.on('disconnect', () => {
      this.connected = false;
      logger.warn('Disconnected from MQTT broker');
    });
    
    this.client.on('error', (err) => {
      logger.error({ err }, 'MQTT error');
    });
    
    this.client.on('message', (topic, message) => {
      try {
        const data = JSON.parse(message.toString());
        const handler = this.subscriptions.get(topic);
        if (handler) {
          handler(data);
        }
      } catch (error) {
        logger.error({ error, topic }, 'Failed to process MQTT message');
      }
    });
  }

  publish(topic: string, data: any): void {
    if (!this.connected) {
      logger.warn({ topic }, 'Not connected to MQTT broker, message not sent');
      return;
    }
    
    const message = JSON.stringify(data);
    this.client.publish(topic, message, { qos: 1 }, (err) => {
      if (err) {
        logger.error({ err, topic }, 'Failed to publish MQTT message');
      }
    });
  }

  subscribe(topic: string, handler: (data: any) => void): void {
    this.subscriptions.set(topic, handler);
    
    if (this.connected) {
      this.client.subscribe(topic, (err) => {
        if (err) {
          logger.error({ err, topic }, 'Failed to subscribe to topic');
          this.subscriptions.delete(topic);
        } else {
          logger.info({ topic }, 'Subscribed to MQTT topic');
        }
      });
    }
  }

  unsubscribe(topic: string): void {
    this.subscriptions.delete(topic);
    
    if (this.connected) {
      this.client.unsubscribe(topic, (err) => {
        if (err) {
          logger.error({ err, topic }, 'Failed to unsubscribe from topic');
        }
      });
    }
  }

  // Moisture-specific publishing methods
  publishMoistureReading(reading: MoistureReading): void {
    // Publish to sensor-specific topic
    this.publish(`moisture/sensors/${reading.sensorId}/data`, {
      timestamp: reading.timestamp,
      surface: reading.moistureSurfacePct,
      deep: reading.moistureDeepPct,
      tempSurface: reading.tempSurfaceC,
      tempDeep: reading.tempDeepC,
      ambientHumidity: reading.ambientHumidityPct,
      ambientTemp: reading.ambientTempC,
      flood: reading.floodStatus,
      quality: reading.qualityScore,
    });
    
    // Publish to general moisture topic
    this.publish('moisture/data', {
      sensorId: reading.sensorId,
      timestamp: reading.timestamp,
      surface: reading.moistureSurfacePct,
      deep: reading.moistureDeepPct,
      flood: reading.floodStatus,
    });
    
    // Publish location updates if available
    if (reading.location) {
      this.publish(`moisture/sensors/${reading.sensorId}/location`, {
        timestamp: reading.timestamp,
        lat: reading.location.lat,
        lng: reading.location.lng,
      });
    }
  }

  publishMoistureAlert(alert: MoistureAlert): void {
    // Publish to alert topic hierarchy
    this.publish(`moisture/alerts/${alert.severity}`, alert);
    this.publish(`moisture/alerts/${alert.type}`, alert);
    this.publish(`moisture/sensors/${alert.sensorId}/alerts`, alert);
  }

  publishAnalytics(sensorId: string, analytics: any): void {
    this.publish(`moisture/analytics/${sensorId}`, analytics);
  }

  // Subscribe to sensor data from the ingestion service
  subscribeSensorData(handler: (data: any) => void): void {
    this.subscribe('sensors/moisture/+/data', handler);
  }

  close(): void {
    if (this.connected) {
      this.client.end();
    }
  }
}