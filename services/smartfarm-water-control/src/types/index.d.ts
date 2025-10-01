// Smart Farm Water Control Type Definitions

export type Brand<T, B> = T & { __brand: B };

export type PlotId = Brand<string, 'PlotId'>;
export type SensorId = Brand<string, 'SensorId'>;
export type ValveId = Brand<string, 'ValveId'>;

export type SensorType = 'AWD' | 'MOISTURE';
export type ValveState = 'ON' | 'OFF' | 'UNKNOWN';
export type ValveAction = 'ON' | 'OFF' | 'MAINTAIN';
export type ControlMode = 'AWD' | 'MOISTURE';

export interface PlotConfiguration {
  plotId: PlotId;
  areaRai: number;
  controlMode: ControlMode;
  sensorId: SensorId;
  valveName: string;
}

export interface WaterDemand {
  plotId: PlotId;
  date: Date;
  demandCubicMeters: number;
  cropType: string;
  growthStage: string;
  et0: number;
  kc: number;
  effectiveRainfall: number;
}

export interface DailyProgress {
  plotId: PlotId;
  date: Date;
  plannedDemand: number;
  actualUsage: number;
  efficiency: number;
  lastUpdated: Date;
}

export interface SensorReading {
  sensorId: SensorId;
  plotId: PlotId;
  timestamp: Date;
  value: number;
  unit: string;
}

export interface WaterLevelReading extends SensorReading {
  waterLevelCm: number;
}

export interface MoistureReading extends SensorReading {
  moisturePercent: number;
  depth: number;
}

export interface ValveCommand {
  valveName: string;
  valveLevel: 0 | 1;  // 0=OFF, 1=ON
  startDateTime: Date;
  plotId: PlotId;
  reason: string;
}

export interface IrrigationCycle {
  plotId: PlotId;
  startTime: Date;
  endTime: Date | null;
  volumeLiters: number | null;
  valveName: string;
  controlMode: ControlMode;
  triggerValue: number;
}

export interface WaterBalance {
  plotId: PlotId;
  date: Date;
  totalUsageLiters: number;
  numberOfCycles: number;
  averageCycleDurationMinutes: number;
  efficiency: number;
}

export interface ControlDecision {
  plotId: PlotId;
  timestamp: Date;
  action: ValveAction;
  reason: string;
  currentValue: number;
  thresholds: {
    low?: number;
    high?: number;
    min?: number;
    max?: number;
  };
  metadata?: Record<string, any>;
}

export interface AWDParameters {
  minWaterLevelCm: number;
  maxWaterLevelCm: number;
  dryingPeriodDays: number;
}

export interface MoistureParameters {
  thresholdLowPercent: number;
  thresholdHighPercent: number;
}

export interface ServiceConfig {
  plots: PlotConfiguration[];
  awdParams: AWDParameters;
  moistureParams: MoistureParameters;
  controlLoopIntervalMinutes: number;
  planningIntervalHours: number;
  waterFlowRateLPM: number;
}