import { WaterLevelReading, WaterLevelAlert } from '../models/water-level.model';
export declare class MqttService {
    private client;
    private connected;
    private subscriptions;
    constructor();
    private setupEventHandlers;
    publish(topic: string, data: any): void;
    subscribe(topic: string, handler: (data: any) => void): void;
    unsubscribe(topic: string): void;
    publishWaterLevelReading(reading: WaterLevelReading): void;
    publishWaterLevelAlert(alert: WaterLevelAlert): void;
    publishAnalytics(sensorId: string, analytics: any): void;
    publishGateRecommendation(gateId: string, recommendation: any): void;
    subscribeSensorData(handler: (data: any) => void): void;
    subscribeGateCommands(handler: (data: any) => void): void;
    close(): void;
}
//# sourceMappingURL=mqtt.service.d.ts.map