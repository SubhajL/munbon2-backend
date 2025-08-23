import { ROSCalculationInput, ROSCalculationOutput, VisualizationData } from '../types';
import { ICalculation } from '../models/calculationModel';
export declare class CalculationService {
    private readonly PERCOLATION_RATE;
    private readonly RAI_TO_M2;
    private readonly CACHE_TTL;
    /**
     * Calculate water demand for given inputs
     */
    calculateWaterDemand(input: ROSCalculationInput): Promise<ROSCalculationOutput>;
    /**
     * Calculate details for each planting
     */
    private calculatePlantingDetails;
    /**
     * Calculate weighted average Kc
     */
    private calculateWeightedKc;
    /**
     * Calculate water requirement
     */
    private calculateWaterRequirement;
    /**
     * Calculate net irrigation requirement
     */
    private calculateNetIrrigation;
    /**
     * Calculate non-agricultural demand
     */
    private calculateNonAgriculturalDemand;
    /**
     * Calculate days since planting
     */
    private calculateDaysSincePlanting;
    /**
     * Determine growth stage name
     */
    private determineGrowthStage;
    /**
     * Validate input parameters
     */
    private validateInput;
    /**
     * Generate cache key
     */
    private generateCacheKey;
    /**
     * Get from cache
     */
    private getFromCache;
    /**
     * Save to cache
     */
    private saveToCache;
    /**
     * Save calculation to database
     */
    saveCalculation(data: any): Promise<ICalculation>;
    /**
     * Get calculation by ID
     */
    getCalculationById(id: string): Promise<ICalculation | null>;
    /**
     * Get calculation history
     */
    getCalculationHistory(params: {
        page: number;
        limit: number;
        startDate?: Date;
        endDate?: Date;
        cropType?: string;
    }): Promise<{
        calculations: ICalculation[];
        total: number;
        page: number;
        limit: number;
        totalPages: number;
    }>;
    /**
     * Get demand pattern for visualization
     */
    getDemandPattern(params: {
        cropType: string;
        year: number;
        period: 'daily' | 'weekly' | 'monthly';
    }): Promise<VisualizationData>;
    /**
     * Get seasonal analysis
     */
    getSeasonalAnalysis(year: number): Promise<{
        seasons: Array<{
            name: string;
            months: number[];
            totalDemand: number;
            averageDemand: number;
            peakDemand: number;
        }>;
        annualTotal: number;
    }>;
}
export declare const calculationService: CalculationService;
//# sourceMappingURL=calculationService.d.ts.map