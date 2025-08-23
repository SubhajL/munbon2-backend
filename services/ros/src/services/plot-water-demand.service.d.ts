import { SeasonalWaterDemandResult, CropType } from '../types';
export interface PlotInfo {
    plotId: string;
    plotCode?: string;
    areaRai: number;
    parentSectionId?: string;
    parentZoneId?: string;
    aosStation: string;
    province: string;
}
export interface PlotCropSchedule {
    plotId: string;
    cropType: CropType;
    plantingDate: Date;
    expectedHarvestDate?: Date;
    season: 'wet' | 'dry';
    year: number;
    status: 'planned' | 'active' | 'harvested';
}
export interface PlotWaterDemandInput {
    plotId: string;
    cropType: CropType;
    plantingDate: Date;
    includeRainfall?: boolean;
    includeLandPreparation?: boolean;
}
export interface BatchPlotWaterDemandInput {
    plotIds: string[];
    cropType: CropType;
    plantingDate: Date;
    includeRainfall?: boolean;
    includeLandPreparation?: boolean;
}
export declare class PlotWaterDemandService {
    /**
     * Get plot information
     */
    getPlotInfo(plotId: string): Promise<PlotInfo | null>;
    /**
     * Calculate water demand for a single plot
     */
    calculatePlotWaterDemand(input: PlotWaterDemandInput): Promise<SeasonalWaterDemandResult>;
    /**
     * Calculate water demand for multiple plots (batch)
     */
    calculateBatchPlotWaterDemand(input: BatchPlotWaterDemandInput): Promise<Map<string, SeasonalWaterDemandResult>>;
    /**
     * Get water demand for plots by zone or section
     */
    getPlotsByArea(areaType: 'zone' | 'section', areaId: string): Promise<PlotInfo[]>;
    /**
     * Save plot seasonal demand to database
     */
    private savePlotSeasonalDemand;
    /**
     * Save plot weekly demands to database
     */
    private savePlotWeeklyDemands;
    /**
     * Determine season based on planting date
     */
    private determineSeason;
    /**
     * Get historical water demand for a plot
     */
    getPlotHistoricalDemand(plotId: string, startYear?: number, endYear?: number): Promise<any[]>;
    /**
     * Get current week water demand for active plots
     */
    getCurrentWeekDemandForActivePlots(currentWeek: number, currentYear: number): Promise<any[]>;
}
export declare const plotWaterDemandService: PlotWaterDemandService;
//# sourceMappingURL=plot-water-demand.service.d.ts.map