import { WaterLevelReading, MoistureReading, GISWaterLevel, SensorStatus, FieldSensorConfig } from '../types/sensor.types';
export declare class SensorRepository {
    private timescalePool;
    private postgresPool;
    getLatestWaterLevel(fieldId: string): Promise<WaterLevelReading | null>;
    getWaterLevelHistory(fieldId: string, startTime: Date, endTime: Date): Promise<WaterLevelReading[]>;
    getLatestMoistureReading(fieldId: string): Promise<MoistureReading | null>;
    getMoistureHistory(fieldId: string, startTime: Date, endTime: Date): Promise<MoistureReading[]>;
    getGISWaterLevel(fieldId: string): Promise<GISWaterLevel | null>;
    getFieldSensorConfig(fieldId: string): Promise<FieldSensorConfig>;
    getSensorStatus(sensorId: string): Promise<SensorStatus | null>;
    updateSensorLastReading(sensorId: string, readingTime: Date): Promise<void>;
}
export declare const sensorRepository: SensorRepository;
//# sourceMappingURL=sensor.repository.d.ts.map