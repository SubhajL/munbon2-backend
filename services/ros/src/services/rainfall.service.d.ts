export interface RainfallData {
    date: Date;
    areaId: string;
    rainfallMm: number;
    effectiveRainfallMm: number;
    source: 'manual' | 'weather_api' | 'sensor';
}
export declare class RainfallService {
    /**
     * Get effective rainfall for a specific area and date
     * Effective rainfall = Total rainfall * efficiency factor
     */
    getEffectiveRainfall(areaId: string, date: Date, efficiencyFactor?: number): Promise<number>;
    /**
     * Get weekly effective rainfall
     */
    getWeeklyEffectiveRainfall(areaId: string, weekStartDate: Date, efficiencyFactor?: number): Promise<number>;
    /**
     * Save rainfall data manually
     */
    saveRainfallData(data: RainfallData): Promise<void>;
    /**
     * Get manual rainfall data from database
     */
    private getManualRainfall;
    /**
     * Get rainfall from weather service
     */
    private getWeatherServiceRainfall;
    /**
     * Import historical rainfall data
     */
    importHistoricalRainfall(data: Array<{
        areaId: string;
        date: Date;
        rainfallMm: number;
    }>, efficiencyFactor?: number): Promise<void>;
    /**
     * Get rainfall statistics for an area
     */
    getRainfallStatistics(areaId: string, startDate: Date, endDate: Date): Promise<{
        totalRainfall: number;
        averageDailyRainfall: number;
        rainyDays: number;
        maxDailyRainfall: number;
    }>;
}
export declare const rainfallService: RainfallService;
//# sourceMappingURL=rainfall.service.d.ts.map