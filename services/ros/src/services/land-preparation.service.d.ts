import { CropType, WaterDemandResult } from '../types';
export interface LandPreparationData {
    cropType: CropType;
    preparationWaterMm: number;
    preparationWeeks: number;
    description?: string;
}
export declare class LandPreparationService {
    private readonly RAI_TO_M3_FACTOR;
    /**
     * Get land preparation water requirements for a crop type
     */
    getLandPreparationRequirements(cropType: CropType): Promise<LandPreparationData>;
    /**
     * Calculate land preparation water demand
     */
    calculateLandPreparationDemand(cropType: CropType, areaRai: number, areaId: string, areaType: string, plantingDate: Date): Promise<WaterDemandResult>;
    /**
     * Save land preparation calculation to database
     */
    private saveLandPreparationCalculation;
    /**
     * Get week number from date
     */
    private getWeekNumber;
}
export declare const landPreparationService: LandPreparationService;
//# sourceMappingURL=land-preparation.service.d.ts.map