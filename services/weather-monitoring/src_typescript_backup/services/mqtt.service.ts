import mqtt from 'mqtt';
import { config } from '../config';
import { logger } from '../utils/logger';
import { EventEmitter } from 'events';
import { WeatherReading, WeatherAlert } from '../models/weather.model';

export class MqttService extends EventEmitter {
  private client: mqtt.MqttClient | null = null;
  private connected: boolean = false;
  private reconnectAttempts: number = 0;
  private readonly maxReconnectAttempts: number = 10;

  constructor() {
    super();
  }

  async connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      const options: mqtt.IClientOptions = {
        host: config.mqtt.host,
        port: config.mqtt.port,
        protocol: config.mqtt.protocol as any,
        username: config.mqtt.username,
        password: config.mqtt.password,
        clientId: `weather-monitoring-${Date.now()}`,
        clean: true,
        connectTimeout: 30000,
        reconnectPeriod: 5000,
        queueQoSZero: false,
        will: {
          topic: 'weather/service/status',
          payload: JSON.stringify({ status: 'offline', timestamp: new Date() }),
          qos: 1,
          retain: true,
        },
      };

      this.client = mqtt.connect(options);

      this.client.on('connect', () => {
        this.connected = true;
        this.reconnectAttempts = 0;
        logger.info('Connected to MQTT broker');
        
        // Publish online status
        this.publishStatus('online');
        
        // Subscribe to topics
        this.subscribeToTopics();
        
        resolve();
      });

      this.client.on('error', (error) => {
        logger.error({ error }, 'MQTT error');
        if (this.reconnectAttempts === 0) {
          reject(error);
        }
      });

      this.client.on('offline', () => {
        this.connected = false;
        logger.warn('MQTT client offline');
      });

      this.client.on('reconnect', () => {
        this.reconnectAttempts++;
        if (this.reconnectAttempts > this.maxReconnectAttempts) {
          logger.error('Max MQTT reconnection attempts reached');
          this.client?.end();
        }
      });

      this.client.on('message', (topic, message) => {
        this.handleMessage(topic, message);
      });
    });
  }

  private subscribeToTopics(): void {
    if (!this.client || !this.connected) return;

    const topics = [
      'weather/commands/+',
      'weather/request/+',
      'sensor/weather/+/data',
    ];

    topics.forEach(topic => {
      this.client!.subscribe(topic, { qos: 1 }, (err) => {
        if (err) {
          logger.error({ err, topic }, 'Failed to subscribe to topic');
        } else {
          logger.info({ topic }, 'Subscribed to topic');
        }
      });
    });
  }

  private handleMessage(topic: string, message: Buffer): void {
    try {
      const payload = JSON.parse(message.toString());
      logger.debug({ topic, payload }, 'Received MQTT message');

      if (topic.startsWith('weather/commands/')) {
        this.handleCommand(topic, payload);
      } else if (topic.startsWith('weather/request/')) {
        this.handleRequest(topic, payload);
      } else if (topic.startsWith('sensor/weather/')) {
        this.handleSensorData(topic, payload);
      }
    } catch (error) {
      logger.error({ error, topic }, 'Failed to handle MQTT message');
    }
  }

  private handleCommand(topic: string, payload: any): void {
    const command = topic.split('/').pop();
    
    switch (command) {
      case 'refresh':
        this.emit('refresh', payload);
        break;
      case 'invalidate-cache':
        this.emit('invalidate-cache', payload);
        break;
      case 'update-config':
        this.emit('update-config', payload);
        break;
      default:
        logger.warn({ command }, 'Unknown command');
    }
  }

  private handleRequest(topic: string, payload: any): void {
    const request = topic.split('/').pop();
    
    switch (request) {
      case 'current':
        this.emit('request-current', payload);
        break;
      case 'forecast':
        this.emit('request-forecast', payload);
        break;
      case 'analytics':
        this.emit('request-analytics', payload);
        break;
      case 'irrigation':
        this.emit('request-irrigation', payload);
        break;
      default:
        logger.warn({ request }, 'Unknown request');
    }
  }

  private handleSensorData(topic: string, payload: any): void {
    const parts = topic.split('/');
    const stationId = parts[2];
    
    this.emit('sensor-data', {
      stationId,
      data: payload,
    });
  }

  async publishWeatherData(reading: WeatherReading): Promise<void> {
    if (!this.connected || !this.client) {
      logger.warn('Cannot publish - MQTT not connected');
      return;
    }

    const topic = `weather/data/${reading.stationId}`;
    const payload = JSON.stringify({
      ...reading,
      timestamp: reading.timestamp.toISOString(),
    });

    return new Promise((resolve, reject) => {
      this.client!.publish(topic, payload, { qos: 1, retain: false }, (err) => {
        if (err) {
          logger.error({ err, topic }, 'Failed to publish weather data');
          reject(err);
        } else {
          logger.debug({ topic, stationId: reading.stationId }, 'Published weather data');
          resolve();
        }
      });
    });
  }

  async publishWeatherAlert(alert: WeatherAlert): Promise<void> {
    if (!this.connected || !this.client) {
      logger.warn('Cannot publish - MQTT not connected');
      return;
    }

    const topic = `weather/alerts/${alert.type}`;
    const payload = JSON.stringify({
      ...alert,
      timestamp: alert.timestamp.toISOString(),
      validFrom: alert.validFrom.toISOString(),
      validUntil: alert.validUntil.toISOString(),
    });

    return new Promise((resolve, reject) => {
      this.client!.publish(topic, payload, { qos: 2, retain: true }, (err) => {
        if (err) {
          logger.error({ err, topic }, 'Failed to publish weather alert');
          reject(err);
        } else {
          logger.info({ topic, alertId: alert.id, type: alert.type }, 'Published weather alert');
          resolve();
        }
      });
    });
  }

  async publishForecast(location: { lat: number; lng: number }, forecast: any): Promise<void> {
    if (!this.connected || !this.client) {
      logger.warn('Cannot publish - MQTT not connected');
      return;
    }

    const topic = `weather/forecast/${location.lat}_${location.lng}`;
    const payload = JSON.stringify({
      location,
      forecast,
      timestamp: new Date().toISOString(),
    });

    return new Promise((resolve, reject) => {
      this.client!.publish(topic, payload, { qos: 1, retain: true }, (err) => {
        if (err) {
          logger.error({ err, topic }, 'Failed to publish forecast');
          reject(err);
        } else {
          logger.debug({ topic, location }, 'Published forecast');
          resolve();
        }
      });
    });
  }

  async publishAnalytics(location: { lat: number; lng: number }, analytics: any): Promise<void> {
    if (!this.connected || !this.client) {
      logger.warn('Cannot publish - MQTT not connected');
      return;
    }

    const topic = `weather/analytics/${location.lat}_${location.lng}`;
    const payload = JSON.stringify({
      location,
      analytics,
      timestamp: new Date().toISOString(),
    });

    return new Promise((resolve, reject) => {
      this.client!.publish(topic, payload, { qos: 0, retain: false }, (err) => {
        if (err) {
          logger.error({ err, topic }, 'Failed to publish analytics');
          reject(err);
        } else {
          logger.debug({ topic, location }, 'Published analytics');
          resolve();
        }
      });
    });
  }

  async publishIrrigationRecommendation(recommendation: any): Promise<void> {
    if (!this.connected || !this.client) {
      logger.warn('Cannot publish - MQTT not connected');
      return;
    }

    const topic = `weather/irrigation/${recommendation.location.lat}_${recommendation.location.lng}`;
    const payload = JSON.stringify({
      ...recommendation,
      timestamp: new Date().toISOString(),
    });

    return new Promise((resolve, reject) => {
      this.client!.publish(topic, payload, { qos: 1, retain: true }, (err) => {
        if (err) {
          logger.error({ err, topic }, 'Failed to publish irrigation recommendation');
          reject(err);
        } else {
          logger.info({ topic, location: recommendation.location }, 'Published irrigation recommendation');
          resolve();
        }
      });
    });
  }

  private publishStatus(status: 'online' | 'offline'): void {
    if (!this.client) return;

    const payload = JSON.stringify({
      service: 'weather-monitoring',
      status,
      timestamp: new Date().toISOString(),
      version: process.env.npm_package_version || '1.0.0',
    });

    this.client.publish('weather/service/status', payload, { qos: 1, retain: true });
  }

  async disconnect(): Promise<void> {
    return new Promise((resolve) => {
      if (!this.client) {
        resolve();
        return;
      }

      this.publishStatus('offline');
      
      this.client.end(false, {}, () => {
        this.connected = false;
        logger.info('Disconnected from MQTT broker');
        resolve();
      });
    });
  }

  isConnected(): boolean {
    return this.connected;
  }
}