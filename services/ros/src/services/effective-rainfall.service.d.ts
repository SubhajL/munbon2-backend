export interface EffectiveRainfallResult {
    monthlyEffectiveRainfall: number;
    weeklyEffectiveRainfall: number;
    cropType: 'rice' | 'field_crop';
    month: number;
    year: number;
    week: number;
}
export declare class EffectiveRainfallService {
    /**
     * Get effective rainfall based on Excel data for specific crop type and time period
     * This uses pre-calculated effective rainfall values from the Thai Excel sheet
     */
    getEffectiveRainfall(cropType: string, calendarWeek: number, calendarYear: number, aosStation?: string, province?: string): Promise<EffectiveRainfallResult>;
    /**
     * Get monthly effective rainfall from database
     */
    private getMonthlyEffectiveRainfall;
    /**
     * Determine crop category for effective rainfall lookup
     */
    private getCropCategory;
    /**
     * Get default effective rainfall values (fallback)
     * Based on Excel data: ฝนใช้การรายวัน sheet
     */
    private getDefaultEffectiveRainfall;
    /**
     * Get number of days in a month
     */
    private getDaysInMonth;
    /**
     * Get effective rainfall for a date range
     */
    getEffectiveRainfallForPeriod(cropType: string, startDate: Date, endDate: Date, aosStation?: string, province?: string): Promise<{
        totalEffectiveRainfall: number;
        weeklyBreakdown: EffectiveRainfallResult[];
    }>;
}
export declare const effectiveRainfallService: EffectiveRainfallService;
//# sourceMappingURL=effective-rainfall.service.d.ts.map