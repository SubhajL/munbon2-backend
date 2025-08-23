export type PlantingMethod = 'transplanted' | 'direct-seeded';
export type AWDPhase = 'wetting' | 'drying' | 'preparation' | 'harvest';
export interface AWDSchedulePhase {
    week: number;
    phase: AWDPhase;
    targetWaterLevel: number;
    duration: number;
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
    amount: number;
    timestamp: Date;
    forecast?: {
        expectedAmount: number;
        probability: number;
        forecastDate: Date;
    }[];
}
export declare const TRANSPLANTED_SCHEDULE: AWDSchedule;
export declare const DIRECT_SEEDED_SCHEDULE: AWDSchedule;
//# sourceMappingURL=awd-control.types.d.ts.map