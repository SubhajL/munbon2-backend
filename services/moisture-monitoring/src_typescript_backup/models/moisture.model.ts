export interface MoistureReading {
  sensorId: string;
  timestamp: Date;
  location?: {
    lat: number;
    lng: number;
  };
  moistureSurfacePct: number;
  moistureDeepPct: number;
  tempSurfaceC: number;
  tempDeepC: number;
  ambientHumidityPct: number;
  ambientTempC: number;
  floodStatus: boolean;
  voltage?: number;
  qualityScore?: number;
}

export interface MoistureAggregation {
  sensorId: string;
  bucket: Date;
  avgMoistureSurface: number;
  avgMoistureDeep: number;
  minMoistureSurface: number;
  minMoistureDeep: number;
  maxMoistureSurface: number;
  maxMoistureDeep: number;
  avgTempSurface: number;
  avgTempDeep: number;
  avgAmbientHumidity: number;
  avgAmbientTemp: number;
  floodDetectedCount: number;
  readingCount: number;
}

export interface MoistureAlert {
  id?: string;
  sensorId: string;
  type: MoistureAlertType;
  severity: AlertSeverity;
  value: number;
  threshold: number;
  message: string;
  timestamp: Date;
  acknowledged: boolean;
  acknowledgedBy?: string;
  acknowledgedAt?: Date;
}

export enum MoistureAlertType {
  LOW_MOISTURE = 'LOW_MOISTURE',
  CRITICAL_LOW_MOISTURE = 'CRITICAL_LOW_MOISTURE',
  HIGH_MOISTURE = 'HIGH_MOISTURE',
  FLOOD_DETECTED = 'FLOOD_DETECTED',
  SENSOR_OFFLINE = 'SENSOR_OFFLINE',
  BATTERY_LOW = 'BATTERY_LOW',
}

export enum AlertSeverity {
  INFO = 'info',
  WARNING = 'warning',
  CRITICAL = 'critical',
}

export interface MoistureSensor {
  sensorId: string;
  gatewayId: string;
  location?: {
    lat: number;
    lng: number;
  };
  lastReading?: MoistureReading;
  lastSeen: Date;
  isActive: boolean;
  metadata?: {
    model?: string;
    installationDate?: Date;
    fieldId?: string;
    cropType?: string;
    soilType?: string;
    [key: string]: any;
  };
}

export interface MoistureAnalytics {
  sensorId: string;
  period: string; // '1h', '1d', '7d', '30d'
  startTime: Date;
  endTime: Date;
  stats: {
    avgMoistureSurface: number;
    avgMoistureDeep: number;
    stdDevMoistureSurface: number;
    stdDevMoistureDeep: number;
    minMoistureSurface: number;
    maxMoistureSurface: number;
    minMoistureDeep: number;
    maxMoistureDeep: number;
    floodEvents: number;
    dataCompleteness: number; // percentage of expected readings
  };
  trends: {
    moistureSurfaceTrend: 'increasing' | 'decreasing' | 'stable';
    moistureDeepTrend: 'increasing' | 'decreasing' | 'stable';
    trendStrength: number; // 0-1
  };
}

export interface MoistureFieldAnalytics {
  fieldId: string;
  period: string;
  sensors: string[];
  aggregatedStats: {
    avgMoisture: number;
    moistureVariability: number;
    irrigationEfficiency: number;
    optimalMoisturePercentage: number;
  };
  recommendations: {
    action: 'irrigate' | 'stop_irrigation' | 'maintain' | 'check_sensors';
    confidence: number;
    reason: string;
  }[];
}