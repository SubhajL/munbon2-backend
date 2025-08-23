export declare class KcService {
    /**
     * Get Kc value for a specific crop and growth week
     */
    getKc(cropType: string, growthWeek: number): Promise<number>;
    /**
     * Get crop duration in weeks
     */
    getCropDuration(cropType: string): Promise<number>;
    /**
     * Import Kc data from Excel structure
     */
    importKcData(data: Array<{
        cropType: string;
        growthWeek: number;
        kcValue: number;
        growthStage?: string;
    }>): Promise<void>;
    /**
     * Get default Kc values based on typical patterns
     */
    private getDefaultKc;
    /**
     * Get all Kc values for a crop
     */
    getKcCurve(cropType: string): Promise<Array<{
        week: number;
        kc: number;
        stage: string;
    }>>;
    /**
     * Get growth stage name based on week and duration
     */
    private getGrowthStageName;
    /**
     * Get available crops
     */
    getAvailableCrops(): Promise<string[]>;
    /**
     * Get crop information
     */
    getCropInfo(cropType: string): Promise<{
        cropType: string;
        duration: number;
        stages: Array<{
            stage: string;
            weeks: number[];
            averageKc: number;
        }>;
        totalWaterRequirement?: number;
    }>;
}
export declare const kcService: KcService;
//# sourceMappingURL=kcService.d.ts.map