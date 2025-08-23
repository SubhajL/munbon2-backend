export interface SensorDataQuery {
    fieldId?: string;
    sensorId?: string;
    startDate?: Date;
    endDate?: Date;
    limit?: number;
}
export interface SensorRegistration {
    sensorId: string;
    fieldId: string;
    type: 'water_level' | 'moisture';
    macAddress?: string;
    metadata?: any;
}
declare class SensorDataIntegration {
    private client;
    constructor();
    getWaterLevelReadings(query: SensorDataQuery): Promise<any>;
    getMoistureReadings(query: SensorDataQuery): Promise<any>;
    registerSensor(registration: SensorRegistration): Promise<any>;
    getSensorStatus(sensorId: string): Promise<any>;
    subscribeToSensorUpdates(fieldId: string, _callback: (data: any) => void): void;
    healthCheck(): Promise<boolean>;
}
export declare const sensorDataIntegration: SensorDataIntegration;
export {};
//# sourceMappingURL=sensor-data.integration.d.ts.map