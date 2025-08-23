"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.closeKafka = exports.publishMessage = exports.getProducer = exports.initializeKafka = exports.KafkaTopics = void 0;
const kafkajs_1 = require("kafkajs");
const logger_1 = require("../utils/logger");
let kafka;
let producer;
let consumer;
exports.KafkaTopics = {
    AWD_SENSOR_DATA: 'awd.sensor.data',
    AWD_CONTROL_COMMANDS: 'awd.control.commands',
    AWD_IRRIGATION_EVENTS: 'awd.irrigation.events',
    WATER_LEVEL_UPDATES: 'water.level.updates',
    GATE_CONTROL_COMMANDS: 'gate.control.commands',
    ALERT_NOTIFICATIONS: 'alert.notifications',
};
const initializeKafka = async () => {
    try {
        const brokers = (process.env.KAFKA_BROKERS || 'localhost:9092').split(',');
        kafka = new kafkajs_1.Kafka({
            clientId: process.env.KAFKA_CLIENT_ID || 'awd-control-service',
            brokers,
            connectionTimeout: 10000,
            requestTimeout: 30000,
            retry: {
                initialRetryTime: 100,
                retries: 8,
            },
        });
        producer = kafka.producer({
            allowAutoTopicCreation: true,
            transactionTimeout: 30000,
        });
        await producer.connect();
        logger_1.logger.info('Kafka producer connected');
        consumer = kafka.consumer({
            groupId: process.env.KAFKA_GROUP_ID || 'awd-control-group',
            sessionTimeout: 30000,
            heartbeatInterval: 3000,
        });
        await consumer.connect();
        logger_1.logger.info('Kafka consumer connected');
        await subscribeToTopics();
        await startConsumer();
    }
    catch (error) {
        logger_1.logger.error(error, 'Failed to initialize Kafka');
        throw error;
    }
};
exports.initializeKafka = initializeKafka;
const subscribeToTopics = async () => {
    const topics = [
        exports.KafkaTopics.AWD_SENSOR_DATA,
        exports.KafkaTopics.WATER_LEVEL_UPDATES,
    ];
    for (const topic of topics) {
        await consumer.subscribe({ topic, fromBeginning: false });
        logger_1.logger.info(`Subscribed to topic: ${topic}`);
    }
};
const startConsumer = async () => {
    await consumer.run({
        eachMessage: async (payload) => {
            const { topic, partition, message } = payload;
            try {
                const value = message.value?.toString();
                if (!value)
                    return;
                const data = JSON.parse(value);
                switch (topic) {
                    case exports.KafkaTopics.AWD_SENSOR_DATA:
                        await handleAwdSensorData(data);
                        break;
                    case exports.KafkaTopics.WATER_LEVEL_UPDATES:
                        await handleWaterLevelUpdate(data);
                        break;
                    default:
                        logger_1.logger.warn(`Unhandled topic: ${topic}`);
                }
            }
            catch (error) {
                logger_1.logger.error({
                    error,
                    topic,
                    partition,
                    offset: message.offset,
                }, 'Error processing Kafka message');
            }
        },
    });
};
const handleAwdSensorData = async (data) => {
    try {
        const { sensorManagementService } = await Promise.resolve().then(() => __importStar(require('../services/sensor-management.service')));
        await sensorManagementService.processSensorData({
            sensorId: data.sensor_id || data.sensorId,
            fieldId: data.field_id || data.fieldId,
            type: data.type,
            value: data.value,
            timestamp: data.timestamp,
            metadata: data.metadata
        });
    }
    catch (error) {
        logger_1.logger.error({ error, data }, 'Failed to handle AWD sensor data');
    }
};
const handleWaterLevelUpdate = async (data) => {
    try {
        const { sensorManagementService } = await Promise.resolve().then(() => __importStar(require('../services/sensor-management.service')));
        await sensorManagementService.processSensorData({
            sensorId: data.sensor_id || data.sensorId,
            fieldId: data.field_id || data.fieldId,
            type: 'water_level',
            value: data.water_level_cm || data.waterLevelCm,
            timestamp: data.timestamp,
            metadata: {
                temperature: data.temperature,
                humidity: data.humidity,
                batteryVoltage: data.battery_voltage,
                signalStrength: data.signal_strength
            }
        });
    }
    catch (error) {
        logger_1.logger.error({ error, data }, 'Failed to handle water level update');
    }
};
const getProducer = () => {
    if (!producer) {
        throw new Error('Kafka producer not initialized');
    }
    return producer;
};
exports.getProducer = getProducer;
const publishMessage = async (topic, message, key) => {
    try {
        await producer.send({
            topic,
            messages: [
                {
                    key: key || undefined,
                    value: JSON.stringify(message),
                    timestamp: Date.now().toString(),
                },
            ],
        });
        logger_1.logger.debug({
            topic,
            key,
            message,
        }, 'Published message to Kafka');
    }
    catch (error) {
        logger_1.logger.error({
            error,
            topic,
            key,
        }, 'Failed to publish message to Kafka');
        throw error;
    }
};
exports.publishMessage = publishMessage;
const closeKafka = async () => {
    if (producer) {
        await producer.disconnect();
        logger_1.logger.info('Kafka producer disconnected');
    }
    if (consumer) {
        await consumer.disconnect();
        logger_1.logger.info('Kafka consumer disconnected');
    }
};
exports.closeKafka = closeKafka;
//# sourceMappingURL=kafka.js.map