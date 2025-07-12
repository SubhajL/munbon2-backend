export enum SensorType {
  WATER_LEVEL = 'water-level',
  MOISTURE = 'moisture',
  FLOW = 'flow',
  WEATHER = 'weather',
  UNKNOWN = 'unknown'
}

export interface SensorLocation {
  lat: number;
  lng: number;
}

export interface SensorReading {
  sensorId: string;
  sensorType: SensorType;
  timestamp: Date;
  location?: SensorLocation;
  data: any;
  metadata?: any;
  qualityScore: number;
}

export interface WaterLevelReading {
  sensorId: string;
  timestamp: Date;
  location?: SensorLocation;
  levelCm: number;
  voltage?: number;
  rssi?: number;
  temperature?: number;
  qualityScore: number;
}

export interface MoistureReading {
  sensorId: string;
  timestamp: Date;
  location?: SensorLocation;
  moistureSurfacePct: number;
  moistureDeepPct: number;
  tempSurfaceC?: number;
  tempDeepC?: number;
  ambientHumidityPct?: number;
  ambientTempC?: number;
  floodStatus?: boolean;
  voltage?: number;
  qualityScore: number;
}

export interface SensorRegistry {
  sensorId: string;
  sensorType: SensorType;
  manufacturer?: string;
  model?: string;
  installationDate?: Date;
  lastSeen: Date;
  currentLocation?: SensorLocation;
  metadata?: any;
  isActive: boolean;
}

export interface SensorLocationHistory {
  sensorId: string;
  timestamp: Date;
  location: SensorLocation;
  accuracy?: number;
  reason?: string;
}

export interface SensorCalibration {
  sensorId: string;
  calibrationType: string;
  calibrationData: any;
  appliedAt: Date;
  expiresAt?: Date;
}

export interface SensorAlert {
  id?: string;
  sensorId: string;
  alertType: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  value: number;
  threshold: number;
  timestamp: Date;
  acknowledged?: boolean;
  acknowledgedBy?: string;
  acknowledgedAt?: Date;
}