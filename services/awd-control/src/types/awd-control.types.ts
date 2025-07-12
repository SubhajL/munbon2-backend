export type PlantingMethod = 'transplanted' | 'direct-seeded';

export type AWDPhase = 'wetting' | 'drying' | 'preparation' | 'harvest';

export interface AWDSchedulePhase {
  week: number;
  phase: AWDPhase;
  targetWaterLevel: number; // in cm
  duration: number; // in days
  description: string;
  requiresFertilizer?: boolean;
}

export interface AWDSchedule {
  plantingMethod: PlantingMethod;
  totalWeeks: number;
  phases: AWDSchedulePhase[];
}

export interface AWDFieldConfig {
  fieldId: string;
  plantingMethod: PlantingMethod;
  startDate: Date;
  currentWeek: number;
  currentPhase: AWDPhase;
  nextPhaseDate: Date;
  isActive: boolean;
  hasRainfallData: boolean;
  targetWaterLevel: number;
}

export interface AWDControlDecision {
  fieldId: string;
  action: 'start_irrigation' | 'stop_irrigation' | 'maintain' | 'notify';
  reason: string;
  targetWaterLevel?: number;
  estimatedDuration?: number;
  notifications?: AWDNotification[];
}

export interface AWDNotification {
  type: 'fertilizer' | 'phase_change' | 'emergency' | 'maintenance';
  message: string;
  priority: 'high' | 'medium' | 'low';
  scheduledFor?: Date;
}

export interface RainfallData {
  fieldId: string;
  amount: number; // mm
  timestamp: Date;
  forecast?: {
    expectedAmount: number;
    probability: number;
    forecastDate: Date;
  }[];
}

// AWD Schedule Templates
export const TRANSPLANTED_SCHEDULE: AWDSchedule = {
  plantingMethod: 'transplanted',
  totalWeeks: 14,
  phases: [
    { week: 0, phase: 'preparation', targetWaterLevel: 10, duration: 2, description: 'Field Preparation Water Release' },
    { week: 1, phase: 'drying', targetWaterLevel: 0, duration: 7, description: 'First Water Supply Suspension' },
    { week: 2, phase: 'wetting', targetWaterLevel: 10, duration: 14, description: 'First Water Application', requiresFertilizer: true },
    { week: 4, phase: 'drying', targetWaterLevel: 0, duration: 21, description: 'Second Water Supply Suspension' },
    { week: 7, phase: 'wetting', targetWaterLevel: 10, duration: 7, description: 'Second Water Application' },
    { week: 8, phase: 'drying', targetWaterLevel: 0, duration: 14, description: 'Third Water Supply Suspension' },
    { week: 10, phase: 'wetting', targetWaterLevel: 10, duration: 14, description: 'Third Water Application' },
    { week: 12, phase: 'drying', targetWaterLevel: 0, duration: 14, description: 'Fourth Water Supply Suspension' },
    { week: 14, phase: 'harvest', targetWaterLevel: 0, duration: 7, description: 'Harvest Preparation' }
  ]
};

export const DIRECT_SEEDED_SCHEDULE: AWDSchedule = {
  plantingMethod: 'direct-seeded',
  totalWeeks: 15,
  phases: [
    { week: 0, phase: 'preparation', targetWaterLevel: 10, duration: 2, description: 'Field Preparation Water Release' },
    { week: 1, phase: 'drying', targetWaterLevel: 0, duration: 14, description: 'First Water Supply Suspension (10-15cm growth)' },
    { week: 3, phase: 'wetting', targetWaterLevel: 10, duration: 14, description: 'First Water Application', requiresFertilizer: true },
    { week: 5, phase: 'drying', targetWaterLevel: 0, duration: 21, description: 'Second Water Supply Suspension' },
    { week: 8, phase: 'wetting', targetWaterLevel: 10, duration: 7, description: 'Second Water Application' },
    { week: 9, phase: 'drying', targetWaterLevel: 0, duration: 14, description: 'Third Water Supply Suspension' },
    { week: 11, phase: 'wetting', targetWaterLevel: 10, duration: 14, description: 'Third Water Application' },
    { week: 13, phase: 'drying', targetWaterLevel: 0, duration: 14, description: 'Fourth Water Supply Suspension' },
    { week: 15, phase: 'harvest', targetWaterLevel: 0, duration: 7, description: 'Harvest Preparation' }
  ]
};