export declare class RainfallService {
    private readonly RAI_TO_M2;
    /**
     * Get effective rainfall for a specific date and area
     */
    getEffectiveRainfall(date: Date, period: 'daily' | 'weekly' | 'monthly', areaRai: number): Promise<{
        amount_mm: number;
        amount_m3: number;
    }>;
    /**
     * Convert monthly rainfall to different periods
     */
    private convertRainfallToPeriod;
    /**
     * Get default effective rainfall by month (mm)
     */
    private getDefaultEffectiveRainfall;
    /**
     * Import rainfall data from Excel
     */
    importRainfallData(data: Array<{
        location?: string;
        year: number;
        month: number;
        totalRainfall: number;
        effectiveRainfall: number;
        numberOfRainyDays?: number;
    }>): Promise<void>;
    /**
     * Calculate effective rainfall from total rainfall
     * Using FAO method for paddy fields
     */
    calculateEffectiveRainfall(totalRainfall: number): number;
    /**
     * Get annual rainfall pattern
     */
    getAnnualRainfallPattern(year?: number): Promise<Array<{
        month: number;
        monthName: string;
        totalRainfall: number;
        effectiveRainfall: number;
    }>>;
    /**
     * Get default total rainfall (for reference)
     */
    private getDefaultTotalRainfall;
}
export declare const rainfallService: RainfallService;
//# sourceMappingURL=rainfallService.d.ts.map