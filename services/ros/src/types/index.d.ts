export interface MonthlyETo {
    aosStation: string;
    province: string;
    month: number;
    etoValue: number;
}
export interface WeeklyKc {
    cropType: CropType;
    cropWeek: number;
    kcValue: number;
}
export type CropType = 'rice' | 'corn' | 'sugarcane';
export type AreaType = 'project' | 'zone' | 'section' | 'FTO' | 'plot';
export interface WaterDemandInput {
    areaId: string;
    cropType: CropType;
    areaType: AreaType;
    areaRai: number;
    cropWeek: number;
    calendarWeek: number;
    calendarYear: number;
    effectiveRainfall?: number;
    waterLevel?: number;
}
export interface WaterDemandResult {
    areaId: string;
    areaType: AreaType;
    areaRai: number;
    cropType: CropType;
    cropWeek: number;
    calendarWeek: number;
    calendarYear: number;
    monthlyETo: number;
    weeklyETo: number;
    kcValue: number;
    percolation: number;
    cropWaterDemandMm: number;
    cropWaterDemandM3: number;
    effectiveRainfall?: number;
    waterLevel?: number;
    netWaterDemandMm?: number;
    netWaterDemandM3?: number;
}
export interface SeasonalWaterDemandResult {
    areaId: string;
    areaType: AreaType;
    areaRai: number;
    cropType: CropType;
    totalCropWeeks: number;
    plantingDate: Date;
    harvestDate: Date;
    totalWaterDemandMm: number;
    totalWaterDemandM3: number;
    totalEffectiveRainfall?: number;
    totalNetWaterDemandMm?: number;
    totalNetWaterDemandM3?: number;
    landPreparationMm?: number;
    landPreparationM3?: number;
    weeklyDetails?: WaterDemandResult[];
}
export interface AreaInfo {
    areaId: string;
    areaType: AreaType;
    areaName?: string;
    totalAreaRai: number;
    parentAreaId?: string;
    aosStation: string;
    province: string;
}
export interface CropCalendar {
    areaId: string;
    areaType: AreaType;
    cropType: CropType;
    plantingDate: Date;
    expectedHarvestDate?: Date;
    season: 'wet' | 'dry';
    year: number;
    totalCropWeeks: number;
}
//# sourceMappingURL=index.d.ts.map