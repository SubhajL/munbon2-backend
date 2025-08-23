import { MoistureReading, MoistureAggregation, MoistureSensor, MoistureAnalytics } from '../models/moisture.model';
export declare class TimescaleService {
    private pool;
    constructor();
    getLatestReadings(sensorIds?: string[], limit?: number): Promise<MoistureReading[]>;
    getReadingsByTimeRange(sensorId: string, startTime: Date, endTime: Date, limit?: number): Promise<MoistureReading[]>;
    getAggregatedReadings(sensorId: string, startTime: Date, endTime: Date, interval: string): Promise<MoistureAggregation[]>;
    getActiveSensors(): Promise<MoistureSensor[]>;
    getSensorsByLocation(lat: number, lng: number, radiusKm: number): Promise<MoistureSensor[]>;
    getAnalytics(sensorId: string, period: string): Promise<MoistureAnalytics>;
    close(): Promise<void>;
}
//# sourceMappingURL=timescale.service.d.ts.map