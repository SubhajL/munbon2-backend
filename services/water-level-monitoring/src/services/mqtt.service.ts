import mqtt, { MqttClient, IClientOptions } from 'mqtt';
import { config } from '../config';
import { logger } from '../utils/logger';
import { WaterLevelReading, WaterLevelAlert } from '../models/water-level.model';

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

  // Water level-specific publishing methods
  publishWaterLevelReading(reading: WaterLevelReading): void {
    // Publish to sensor-specific topic
    this.publish(`water-level/sensors/${reading.sensorId}/data`, {
      timestamp: reading.timestamp,
      level: reading.levelCm,
      voltage: reading.voltage,
      rssi: reading.rssi,
      temperature: reading.temperature,
      quality: reading.qualityScore,
    });
    
    // Publish to general water level topic
    this.publish('water-level/data', {
      sensorId: reading.sensorId,
      timestamp: reading.timestamp,
      level: reading.levelCm,
      location: reading.location,
    });
    
    // Publish location updates if available
    if (reading.location) {
      this.publish(`water-level/sensors/${reading.sensorId}/location`, {
        timestamp: reading.timestamp,
        lat: reading.location.lat,
        lng: reading.location.lng,
      });
    }
  }

  publishWaterLevelAlert(alert: WaterLevelAlert): void {
    // Publish to alert topic hierarchy
    this.publish(`water-level/alerts/${alert.severity}`, alert);
    this.publish(`water-level/alerts/${alert.type}`, alert);
    this.publish(`water-level/sensors/${alert.sensorId}/alerts`, alert);
  }

  publishAnalytics(sensorId: string, analytics: any): void {
    this.publish(`water-level/analytics/${sensorId}`, analytics);
  }

  publishGateRecommendation(gateId: string, recommendation: any): void {
    this.publish(`water-level/gates/${gateId}/recommendations`, recommendation);
  }

  // Subscribe to sensor data from the ingestion service
  subscribeSensorData(handler: (data: any) => void): void {
    this.subscribe('sensors/water-level/+/data', handler);
  }

  // Subscribe to gate control commands
  subscribeGateCommands(handler: (data: any) => void): void {
    this.subscribe('gates/+/commands', handler);
  }

  close(): void {
    if (this.connected) {
      this.client.end();
    }
  }
}