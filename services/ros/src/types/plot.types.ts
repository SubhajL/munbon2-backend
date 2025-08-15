export interface PlotInfo {
  plotId: string;
  plotCode?: string;
  areaRai: number;
  parentSectionId?: string;
  parentZoneId?: string;
  aosStation?: string;
  province?: string;
  currentPlantingDate?: Date;
  currentCropType?: string;
  currentCropStatus?: 'active' | 'harvested' | 'fallow' | 'planned';
  geometry?: any; // PostGIS geometry
}

export interface PlotCropSchedule {
  id?: number;
  plotId: string;
  cropType: string;
  plantingDate: Date;
  expectedHarvestDate?: Date;
  season: 'wet' | 'dry';
  year: number;
  status: 'planned' | 'active' | 'completed' | 'cancelled';
  createdAt?: Date;
  updatedAt?: Date;
}

export interface UpdatePlotPlantingDateInput {
  plotId: string;
  plantingDate: Date;
  cropType: string;
  season?: 'wet' | 'dry';
  status?: 'planned' | 'active';
}

export interface BatchUpdatePlantingDatesInput {
  plotIds: string[];
  plantingDate: Date;
  cropType: string;
  season?: 'wet' | 'dry';
  status?: 'planned' | 'active';
}

export interface PlotCurrentCropView {
  plotId: string;
  plotCode?: string;
  areaRai: number;
  parentZoneId?: string;
  parentSectionId?: string;
  currentPlantingDate?: Date;
  currentCropType?: string;
  currentCropStatus?: string;
  totalWaterDemandM3?: number;
  totalNetWaterDemandM3?: number;
  landPreparationM3?: number;
  currentCropWeek?: number;
  expectedHarvestDate?: Date;
}