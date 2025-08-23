"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.MqttService = void 0;
const mqtt_1 = __importDefault(require("mqtt"));
const config_1 = require("../config");
const logger_1 = require("../utils/logger");
class MqttService {
    constructor() {
        this.connected = false;
        this.subscriptions = new Map();
        const options = {
            clientId: config_1.config.mqtt.clientId,
            clean: true,
            connectTimeout: 4000,
            reconnectPeriod: config_1.config.mqtt.reconnectPeriod,
        };
        if (config_1.config.mqtt.username) {
            options.username = config_1.config.mqtt.username;
            options.password = config_1.config.mqtt.password;
        }
        this.client = mqtt_1.default.connect(config_1.config.mqtt.brokerUrl, options);
        this.setupEventHandlers();
    }
    setupEventHandlers() {
        this.client.on('connect', () => {
            this.connected = true;
            logger_1.logger.info('Connected to MQTT broker');
            // Resubscribe to topics after reconnection
            this.subscriptions.forEach((_, topic) => {
                this.client.subscribe(topic, (err) => {
                    if (err) {
                        logger_1.logger.error({ err, topic }, 'Failed to resubscribe to topic');
                    }
                });
            });
        });
        this.client.on('disconnect', () => {
            this.connected = false;
            logger_1.logger.warn('Disconnected from MQTT broker');
        });
        this.client.on('error', (err) => {
            logger_1.logger.error({ err }, 'MQTT error');
        });
        this.client.on('message', (topic, message) => {
            try {
                const data = JSON.parse(message.toString());
                const handler = this.subscriptions.get(topic);
                if (handler) {
                    handler(data);
                }
            }
            catch (error) {
                logger_1.logger.error({ error, topic }, 'Failed to process MQTT message');
            }
        });
    }
    publish(topic, data) {
        if (!this.connected) {
            logger_1.logger.warn({ topic }, 'Not connected to MQTT broker, message not sent');
            return;
        }
        const message = JSON.stringify(data);
        this.client.publish(topic, message, { qos: 1 }, (err) => {
            if (err) {
                logger_1.logger.error({ err, topic }, 'Failed to publish MQTT message');
            }
        });
    }
    subscribe(topic, handler) {
        this.subscriptions.set(topic, handler);
        if (this.connected) {
            this.client.subscribe(topic, (err) => {
                if (err) {
                    logger_1.logger.error({ err, topic }, 'Failed to subscribe to topic');
                    this.subscriptions.delete(topic);
                }
                else {
                    logger_1.logger.info({ topic }, 'Subscribed to MQTT topic');
                }
            });
        }
    }
    unsubscribe(topic) {
        this.subscriptions.delete(topic);
        if (this.connected) {
            this.client.unsubscribe(topic, (err) => {
                if (err) {
                    logger_1.logger.error({ err, topic }, 'Failed to unsubscribe from topic');
                }
            });
        }
    }
    // Water level-specific publishing methods
    publishWaterLevelReading(reading) {
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
    publishWaterLevelAlert(alert) {
        // Publish to alert topic hierarchy
        this.publish(`water-level/alerts/${alert.severity}`, alert);
        this.publish(`water-level/alerts/${alert.type}`, alert);
        this.publish(`water-level/sensors/${alert.sensorId}/alerts`, alert);
    }
    publishAnalytics(sensorId, analytics) {
        this.publish(`water-level/analytics/${sensorId}`, analytics);
    }
    publishGateRecommendation(gateId, recommendation) {
        this.publish(`water-level/gates/${gateId}/recommendations`, recommendation);
    }
    // Subscribe to sensor data from the ingestion service
    subscribeSensorData(handler) {
        this.subscribe('sensors/water-level/+/data', handler);
    }
    // Subscribe to gate control commands
    subscribeGateCommands(handler) {
        this.subscribe('gates/+/commands', handler);
    }
    close() {
        if (this.connected) {
            this.client.end();
        }
    }
}
exports.MqttService = MqttService;
//# sourceMappingURL=mqtt.service.js.map