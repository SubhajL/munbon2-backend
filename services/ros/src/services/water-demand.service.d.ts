import { WaterDemandInput, WaterDemandResult, SeasonalWaterDemandResult, CropType } from '../types';
export declare class WaterDemandService {
    private readonly PERCOLATION_MM_PER_WEEK;
    private readonly RAI_TO_M3_FACTOR;
    /**
     * Calculate water demand for a specific crop week
     */
    calculateWaterDemand(input: WaterDemandInput): Promise<WaterDemandResult>;
    /**
     * Calculate water demand for entire crop season
     */
    calculateSeasonalWaterDemand(areaId: string, areaType: string, areaRai: number, cropType: CropType, plantingDate: Date, includeRainfall?: boolean, includeLandPreparation?: boolean): Promise<SeasonalWaterDemandResult>;
    /**
     * Get monthly ETo from database
     */
    private getMonthlyETo;
    /**
     * Calculate weekly ETo from monthly value
     */
    private calculateWeeklyETo;
    /**
     * Get Kc value from database
     */
    private getKcValue;
    /**
     * Get total crop weeks for a crop type
     */
    private getTotalCropWeeks;
    /**
     * Save water demand calculation to database
     */
    private saveWaterDemandCalculation;
    /**
     * Get historical water demand calculations
     */
    getHistoricalWaterDemand(areaId: string, startDate: Date, endDate: Date): Promise<WaterDemandResult[]>;
}
export declare const waterDemandService: WaterDemandService;
//# sourceMappingURL=water-demand.service.d.ts.map