export interface WaterLevelData {
    areaId: string;
    measurementDate: Date;
    measurementTime?: string;
    waterLevelM: number;
    referenceLevel?: string;
    source: 'manual' | 'sensor' | 'scada';
    sensorId?: string;
}
export declare class WaterLevelService {
    /**
     * Get current water level for an area
     */
    getCurrentWaterLevel(areaId: string): Promise<WaterLevelData | null>;
    /**
     * Save water level measurement
     */
    saveWaterLevel(data: WaterLevelData): Promise<void>;
    /**
     * Get water level history for an area
     */
    getWaterLevelHistory(areaId: string, startDate: Date, endDate: Date): Promise<WaterLevelData[]>;
    /**
     * Get average water level for a period
     */
    getAverageWaterLevel(areaId: string, startDate: Date, endDate: Date): Promise<number>;
    /**
     * Check if water level is critical (below threshold)
     */
    checkCriticalLevel(areaId: string, criticalThreshold: number): Promise<{
        isCritical: boolean;
        currentLevel: number | null;
        thresholdDifference: number | null;
    }>;
    /**
     * Import water level data from sensors/SCADA
     */
    importSensorData(data: Array<{
        sensorId: string;
        areaId: string;
        timestamp: Date;
        waterLevel: number;
    }>): Promise<void>;
    /**
     * Get water level statistics
     */
    getWaterLevelStatistics(areaId: string, startDate: Date, endDate: Date): Promise<{
        minLevel: number;
        maxLevel: number;
        avgLevel: number;
        stdDev: number;
        measurementCount: number;
    }>;
}
export declare const waterLevelService: WaterLevelService;
//# sourceMappingURL=water-level.service.d.ts.map