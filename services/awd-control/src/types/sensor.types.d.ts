export interface WaterLevelReading {
    time: Date;
    sensorId: string;
    fieldId: string;
    waterLevelCm: number;
    temperature?: number;
    humidity?: number;
    batteryVoltage?: number;
    signalStrength?: number;
    source: 'sensor' | 'gis';
}
export interface MoistureReading {
    time: Date;
    sensorId: string;
    fieldId: string;
    moisturePercent: number;
    depth: number;
    temperature?: number;
    batteryVoltage?: number;
}
export interface GISWaterLevel {
    fieldId: string;
    plotId: string;
    waterHeightCm: number;
    cropHeightCm: number;
    measurementDate: Date;
    area: number;
    geometry?: any;
}
export interface SensorStatus {
    sensorId: string;
    fieldId: string;
    type: 'water_level' | 'moisture';
    lastReading: Date;
    isActive: boolean;
    reliability: number;
    batteryLevel?: number;
}
export interface FieldSensorConfig {
    fieldId: string;
    hasWaterLevelSensor: boolean;
    hasMoistureSensor: boolean;
    waterLevelSensorIds: string[];
    moistureSensorIds: string[];
    useGISFallback: boolean;
    dryingDayCount?: number;
    lastDryingStartDate?: Date;
}
//# sourceMappingURL=sensor.types.d.ts.map