// Excel-based data types
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

// Water demand calculation input
export interface WaterDemandInput {
  areaId: string;
  cropType: CropType;
  areaType: AreaType;
  areaRai: number;
  cropWeek: number;
  calendarWeek: number;
  calendarYear: number;
  effectiveRainfall?: number;  // mm/week
  waterLevel?: number;          // meters
}

// Water demand calculation result
export interface WaterDemandResult {
  areaId: string;
  areaType: AreaType;
  areaRai: number;
  cropType: CropType;
  cropWeek: number;
  calendarWeek: number;
  calendarYear: number;
  
  // ETo and Kc values
  monthlyETo: number;
  weeklyETo: number;
  kcValue: number;
  percolation: number;
  
  // Calculated values
  cropWaterDemandMm: number;    // (ETo x Kc) + percolation
  cropWaterDemandM3: number;    // mm x area x 1.6
  
  // Optional values with rainfall/water level
  effectiveRainfall?: number;
  waterLevel?: number;
  netWaterDemandMm?: number;
  netWaterDemandM3?: number;
  
  // New fields for weekly water level integration
  weeklyAvgWaterLevel?: number;
  waterLevelAdjustmentFactor?: number;
  adjustedNetDemandMm?: number;
  adjustedNetDemandM3?: number;
  waterLevelDataQuality?: number;
  adjustmentMethod?: string;
}

// Seasonal water demand result
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
  
  // Land preparation water (if included)
  landPreparationMm?: number;
  landPreparationM3?: number;
  
  weeklyDetails?: WaterDemandResult[];
}

// Area information
export interface AreaInfo {
  areaId: string;
  areaType: AreaType;
  areaName?: string;
  totalAreaRai: number;
  parentAreaId?: string;
  aosStation: string;
  province: string;
}

// Crop calendar
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