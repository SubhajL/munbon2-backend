import { WaterLevelReading, WaterLevelAggregation, WaterLevelSensor, WaterLevelAnalytics } from '../models/water-level.model';
export declare class TimescaleService {
    private pool;
    constructor();
    getLatestReadings(sensorIds?: string[], limit?: number): Promise<WaterLevelReading[]>;
    getReadingsByTimeRange(sensorId: string, startTime: Date, endTime: Date, limit?: number): Promise<WaterLevelReading[]>;
    getAggregatedReadings(sensorId: string, startTime: Date, endTime: Date, interval: string): Promise<WaterLevelAggregation[]>;
    getActiveSensors(): Promise<WaterLevelSensor[]>;
    getSensorsByLocation(lat: number, lng: number, radiusKm: number): Promise<WaterLevelSensor[]>;
    getAnalytics(sensorId: string, period: string): Promise<WaterLevelAnalytics>;
    getRateOfChange(sensorId: string, minutes?: number): Promise<number>;
    close(): Promise<void>;
}
//# sourceMappingURL=timescale.service.d.ts.map