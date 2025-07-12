import { Kafka, Producer, Consumer, EachMessagePayload } from 'kafkajs';
import { logger } from '../utils/logger';

let kafka: Kafka;
let producer: Producer;
let consumer: Consumer;

export const KafkaTopics = {
  AWD_SENSOR_DATA: 'awd.sensor.data',
  AWD_CONTROL_COMMANDS: 'awd.control.commands',
  AWD_IRRIGATION_EVENTS: 'awd.irrigation.events',
  WATER_LEVEL_UPDATES: 'water.level.updates',
  GATE_CONTROL_COMMANDS: 'gate.control.commands',
  ALERT_NOTIFICATIONS: 'alert.notifications',
};

export const initializeKafka = async (): Promise<void> => {
  try {
    const brokers = (process.env.KAFKA_BROKERS || 'localhost:9092').split(',');
    
    kafka = new Kafka({
      clientId: process.env.KAFKA_CLIENT_ID || 'awd-control-service',
      brokers,
      connectionTimeout: 10000,
      requestTimeout: 30000,
      retry: {
        initialRetryTime: 100,
        retries: 8,
      },
    });

    // Initialize producer
    producer = kafka.producer({
      allowAutoTopicCreation: true,
      transactionTimeout: 30000,
    });
    
    await producer.connect();
    logger.info('Kafka producer connected');

    // Initialize consumer
    consumer = kafka.consumer({ 
      groupId: process.env.KAFKA_GROUP_ID || 'awd-control-group',
      sessionTimeout: 30000,
      heartbeatInterval: 3000,
    });
    
    await consumer.connect();
    logger.info('Kafka consumer connected');

    // Subscribe to relevant topics
    await subscribeToTopics();
    
    // Start consuming messages
    await startConsumer();
  } catch (error) {
    logger.error(error, 'Failed to initialize Kafka');
    throw error;
  }
};

const subscribeToTopics = async (): Promise<void> => {
  const topics = [
    KafkaTopics.AWD_SENSOR_DATA,
    KafkaTopics.WATER_LEVEL_UPDATES,
  ];

  for (const topic of topics) {
    await consumer.subscribe({ topic, fromBeginning: false });
    logger.info(`Subscribed to topic: ${topic}`);
  }
};

const startConsumer = async (): Promise<void> => {
  await consumer.run({
    eachMessage: async (payload: EachMessagePayload) => {
      const { topic, partition, message } = payload;
      
      try {
        const value = message.value?.toString();
        if (!value) return;

        const data = JSON.parse(value);
        
        switch (topic) {
          case KafkaTopics.AWD_SENSOR_DATA:
            await handleAwdSensorData(data);
            break;
            
          case KafkaTopics.WATER_LEVEL_UPDATES:
            await handleWaterLevelUpdate(data);
            break;
            
          default:
            logger.warn(`Unhandled topic: ${topic}`);
        }
      } catch (error) {
        logger.error({
          error,
          topic,
          partition,
          offset: message.offset,
        }, 'Error processing Kafka message');
      }
    },
  });
};

const handleAwdSensorData = async (data: any): Promise<void> => {
  try {
    const { sensorManagementService } = await import('../services/sensor-management.service');
    
    // Process incoming sensor data
    await sensorManagementService.processSensorData({
      sensorId: data.sensor_id || data.sensorId,
      fieldId: data.field_id || data.fieldId,
      type: data.type,
      value: data.value,
      timestamp: data.timestamp,
      metadata: data.metadata
    });
  } catch (error) {
    logger.error({ error, data }, 'Failed to handle AWD sensor data');
  }
};

const handleWaterLevelUpdate = async (data: any): Promise<void> => {
  try {
    const { sensorManagementService } = await import('../services/sensor-management.service');
    
    // Process water level update
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
  } catch (error) {
    logger.error({ error, data }, 'Failed to handle water level update');
  }
};

export const getProducer = (): Producer => {
  if (!producer) {
    throw new Error('Kafka producer not initialized');
  }
  return producer;
};

export const publishMessage = async (
  topic: string,
  message: any,
  key?: string
): Promise<void> => {
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
    
    logger.debug({
      topic,
      key,
      message,
    }, 'Published message to Kafka');
  } catch (error) {
    logger.error({
      error,
      topic,
      key,
    }, 'Failed to publish message to Kafka');
    throw error;
  }
};

export const closeKafka = async (): Promise<void> => {
  if (producer) {
    await producer.disconnect();
    logger.info('Kafka producer disconnected');
  }
  if (consumer) {
    await consumer.disconnect();
    logger.info('Kafka consumer disconnected');
  }
};