import { WaterLevelReading, MoistureReading, SensorStatus } from '../types/sensor.types';
export declare class SensorManagementService {
    private redis;
    private readonly CACHE_TTL;
    private readonly MOISTURE_THRESHOLD_DRY;
    private readonly DEFAULT_DRYING_DAYS;
    getCurrentWaterLevel(fieldId: string): Promise<WaterLevelReading | null>;
    getCurrentMoistureLevel(fieldId: string): Promise<MoistureReading | null>;
    checkIrrigationNeed(fieldId: string): Promise<{
        needsIrrigation: boolean;
        reason: string;
        data: any;
    }>;
    private getAWDThresholds;
    private getDaysSinceDryingStart;
    getFieldSensorHealth(fieldId: string): Promise<{
        overall: 'healthy' | 'degraded' | 'critical';
        sensors: SensorStatus[];
        issues: string[];
    }>;
    processSensorData(data: {
        sensorId: string;
        fieldId: string;
        type: 'water_level' | 'moisture';
        value: number;
        timestamp: string;
        metadata?: any;
    }): Promise<void>;
}
export declare const sensorManagementService: SensorManagementService;
//# sourceMappingURL=sensor-management.service.d.ts.map