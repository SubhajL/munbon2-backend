import { PlantingMethod, AWDFieldConfig, AWDControlDecision } from '../types/awd-control.types';
export declare class AWDControlService {
    private redis;
    private postgresPool;
    private readonly CRITICAL_MOISTURE_THRESHOLD;
    private readonly RAINFALL_THRESHOLD;
    initializeFieldControl(fieldId: string, plantingMethod: PlantingMethod, startDate: Date): Promise<AWDFieldConfig>;
    makeControlDecision(fieldId: string): Promise<AWDControlDecision>;
    private evaluatePhaseRequirements;
    private evaluateWettingPhase;
    private evaluateDryingPhase;
    private getFieldConfig;
    private updateFieldProgress;
    private getRainfallData;
    private calculateCurrentWeek;
    private getCurrentPhase;
    private calculateNextPhaseDate;
    private getScheduleTemplate;
    private estimateIrrigationDuration;
    getPlantingMethodFromGIS(fieldId: string): Promise<PlantingMethod>;
}
export declare const awdControlService: AWDControlService;
//# sourceMappingURL=awd-control.service.d.ts.map