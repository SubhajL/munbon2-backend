import { Logger } from 'pino';
import { EventEmitter } from 'events';
import mqtt from 'mqtt';

export interface MqttBrokerOptions {
  port: number;
  wsPort: number;
  logger: Logger;
}

/**
 * Simple MQTT broker wrapper for the sensor data service
 * In production, use a dedicated MQTT broker like Mosquitto or HiveMQ
 */
export class MqttBroker extends EventEmitter {
  private logger: Logger;
  private options: MqttBrokerOptions;
  private topics: Map<string, Set<Function>> = new Map();

  constructor(options: MqttBrokerOptions) {
    super();
    this.options = options;
    this.logger = options.logger;
  }

  async start(): Promise<void> {
    // In a real implementation, this would start an MQTT broker
    // For now, we'll just log that it's started
    this.logger.info(`MQTT broker interface started (port ${this.options.port})`);
    this.logger.info(`Note: This is a mock broker. Use Mosquitto or HiveMQ for production`);
  }

  async stop(): Promise<void> {
    this.topics.clear();
    this.logger.info('MQTT broker interface stopped');
  }

  /**
   * Publish a message to a topic
   */
  publish(topic: string, payload: any): void {
    const message = Buffer.from(JSON.stringify(payload));
    
    // Emit to local subscribers
    this.emit('publish', { topic, payload: message });
    
    // Call topic-specific handlers
    const handlers = this.topics.get(topic);
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(topic, message);
        } catch (error) {
          this.logger.error({ error, topic }, 'Error in MQTT handler');
        }
      });
    }
    
    // Check wildcard subscriptions
    this.topics.forEach((handlers, pattern) => {
      if (this.matchTopic(pattern, topic)) {
        handlers.forEach(handler => {
          try {
            handler(topic, message);
          } catch (error) {
            this.logger.error({ error, topic, pattern }, 'Error in wildcard MQTT handler');
          }
        });
      }
    });
    
    this.logger.debug({ topic, payloadSize: message.length }, 'Message published');
  }

  /**
   * Subscribe to a topic
   */
  subscribe(topic: string, handler: Function): void {
    if (!this.topics.has(topic)) {
      this.topics.set(topic, new Set());
    }
    this.topics.get(topic)!.add(handler);
    this.logger.debug({ topic }, 'Subscribed to topic');
  }

  /**
   * Unsubscribe from a topic
   */
  unsubscribe(topic: string, handler: Function): void {
    const handlers = this.topics.get(topic);
    if (handlers) {
      handlers.delete(handler);
      if (handlers.size === 0) {
        this.topics.delete(topic);
      }
    }
    this.logger.debug({ topic }, 'Unsubscribed from topic');
  }

  /**
   * Match MQTT topic patterns
   */
  private matchTopic(pattern: string, topic: string): boolean {
    const patternParts = pattern.split('/');
    const topicParts = topic.split('/');
    
    if (pattern === topic) return true;
    
    for (let i = 0; i < patternParts.length; i++) {
      if (patternParts[i] === '#') {
        return true;
      }
      
      if (patternParts[i] === '+') {
        if (i >= topicParts.length) return false;
        continue;
      }
      
      if (i >= topicParts.length || patternParts[i] !== topicParts[i]) {
        return false;
      }
    }
    
    return patternParts.length === topicParts.length;
  }

  /**
   * Create an MQTT client for external broker connection
   */
  static createClient(brokerUrl: string, options?: mqtt.IClientOptions): mqtt.MqttClient {
    return mqtt.connect(brokerUrl, {
      ...options,
      reconnectPeriod: 5000,
      connectTimeout: 30000
    });
  }
}