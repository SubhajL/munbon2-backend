export interface WaterLevelReading {
  sensorId: string;
  timestamp: Date;
  location?: {
    lat: number;
    lng: number;
  };
  levelCm: number;
  voltage?: number;
  rssi?: number;
  temperature?: number;
  qualityScore?: number;
}

export interface WaterLevelAggregation {
  sensorId: string;
  bucket: Date;
  avgLevel: number;
  minLevel: number;
  maxLevel: number;
  stdDevLevel: number;
  rateOfChange: number; // cm per hour
  readingCount: number;
}

export interface WaterLevelAlert {
  id?: string;
  sensorId: string;
  type: WaterLevelAlertType;
  severity: AlertSeverity;
  value: number;
  threshold: number;
  message: string;
  timestamp: Date;
  acknowledged: boolean;
  acknowledgedBy?: string;
  acknowledgedAt?: Date;
  metadata?: {
    previousValue?: number;
    rateOfChange?: number;
    location?: { lat: number; lng: number };
  };
}

export enum WaterLevelAlertType {
  LOW_WATER = 'LOW_WATER',
  CRITICAL_LOW_WATER = 'CRITICAL_LOW_WATER',
  HIGH_WATER = 'HIGH_WATER',
  CRITICAL_HIGH_WATER = 'CRITICAL_HIGH_WATER',
  RAPID_INCREASE = 'RAPID_INCREASE',
  RAPID_DECREASE = 'RAPID_DECREASE',
  SENSOR_OFFLINE = 'SENSOR_OFFLINE',
  BATTERY_LOW = 'BATTERY_LOW',
  SIGNAL_WEAK = 'SIGNAL_WEAK',
}

export enum AlertSeverity {
  INFO = 'info',
  WARNING = 'warning',
  CRITICAL = 'critical',
}

export interface WaterLevelSensor {
  sensorId: string;
  location?: {
    lat: number;
    lng: number;
  };
  lastReading?: WaterLevelReading;
  lastSeen: Date;
  isActive: boolean;
  metadata?: {
    model?: string;
    manufacturer?: string;
    installationDate?: Date;
    canalId?: string;
    gateId?: string;
    sensorType?: string;
    calibrationData?: any;
    [key: string]: any;
  };
}

export interface WaterLevelAnalytics {
  sensorId: string;
  period: string; // '1h', '1d', '7d', '30d'
  startTime: Date;
  endTime: Date;
  stats: {
    avgLevel: number;
    stdDevLevel: number;
    minLevel: number;
    maxLevel: number;
    totalChange: number;
    avgRateOfChange: number; // cm per hour
    maxRateOfChange: number;
    dataCompleteness: number; // percentage of expected readings
    anomalyCount: number;
  };
  trends: {
    levelTrend: 'increasing' | 'decreasing' | 'stable';
    trendStrength: number; // 0-1
    seasonalPattern?: string;
  };
  predictions?: {
    nextHourLevel?: number;
    confidence?: number;
  };
}

export interface GateControlRecommendation {
  gateId: string;
  sensorId: string;
  currentLevel: number;
  targetLevel: number;
  recommendedAction: 'open' | 'close' | 'maintain';
  recommendedPercentage: number; // 0-100
  reason: string;
  confidence: number; // 0-1
  estimatedTimeToTarget?: number; // minutes
}

export interface WaterFlowEstimate {
  sensorId: string;
  timestamp: Date;
  flowRateCms?: number; // cubic meters per second
  volumeM3?: number; // total volume
  confidence: number;
  method: 'level-change' | 'velocity' | 'gate-position';
}