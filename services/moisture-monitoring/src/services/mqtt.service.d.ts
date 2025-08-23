import { MoistureReading, MoistureAlert } from '../models/moisture.model';
export declare class MqttService {
    private client;
    private connected;
    private subscriptions;
    constructor();
    private setupEventHandlers;
    publish(topic: string, data: any): void;
    subscribe(topic: string, handler: (data: any) => void): void;
    unsubscribe(topic: string): void;
    publishMoistureReading(reading: MoistureReading): void;
    publishMoistureAlert(alert: MoistureAlert): void;
    publishAnalytics(sensorId: string, analytics: any): void;
    subscribeSensorData(handler: (data: any) => void): void;
    close(): void;
}
//# sourceMappingURL=mqtt.service.d.ts.map