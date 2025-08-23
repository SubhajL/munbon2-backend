import { Producer } from 'kafkajs';
export declare const KafkaTopics: {
    AWD_SENSOR_DATA: string;
    AWD_CONTROL_COMMANDS: string;
    AWD_IRRIGATION_EVENTS: string;
    WATER_LEVEL_UPDATES: string;
    GATE_CONTROL_COMMANDS: string;
    ALERT_NOTIFICATIONS: string;
};
export declare const initializeKafka: () => Promise<void>;
export declare const getProducer: () => Producer;
export declare const publishMessage: (topic: string, message: any, key?: string) => Promise<void>;
export declare const closeKafka: () => Promise<void>;
//# sourceMappingURL=kafka.d.ts.map