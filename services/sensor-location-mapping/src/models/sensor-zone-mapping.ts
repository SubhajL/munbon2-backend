export interface Location {
  lat: number;
  lng: number;
}

export interface SensorZoneMapping {
  sensorId: string;
  sensorType: 'water_level' | 'moisture';
  location: Location;
  zoneCode?: string;
  zoneName?: string;
  sectionCode?: string;
  sectionName?: string;
  irrigationBlockId?: string;
  parcelId?: string;
  lastUpdated: Date;
}

export interface ZoneWaterStatus {
  zoneCode: string;
  zoneName: string;
  totalSensors: number;
  waterLevelSensors: SensorWaterLevel[];
  moistureSensors: SensorMoisture[];
  averageWaterLevel?: number;
  averageMoisture?: number;
  cropWaterRequirement?: number;
  deficitPercentage?: number;
  status: 'sufficient' | 'deficit' | 'unknown';
  lastUpdated: Date;
}

export interface SensorWaterLevel {
  sensorId: string;
  location: Location;
  levelCm: number;
  voltage?: number;
  quality: number;
  timestamp: Date;
}

export interface SensorMoisture {
  sensorId: string;
  location: Location;
  moistureSurfacePct: number;
  moistureDeepPct: number;
  floodStatus?: boolean;
  quality: number;
  timestamp: Date;
}

export interface WaterRequirementValidation {
  zoneCode: string;
  cropType: string;
  cropWeek: number;
  requiredWaterLevelCm: number;
  actualWaterLevelCm: number;
  moistureStatus: {
    surface: number;
    deep: number;
    optimal: boolean;
  };
  validationStatus: 'sufficient' | 'deficit' | 'excess';
  deficitCm?: number;
  excessCm?: number;
  recommendations: string[];
  timestamp: Date;
}