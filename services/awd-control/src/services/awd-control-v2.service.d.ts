import { AWDControlDecision } from '../types/awd-control.types';
export declare class AWDControlServiceV2 {
    private redis;
    private postgresPool;
    private readonly CRITICAL_MOISTURE_THRESHOLD;
    private readonly RAINFALL_THRESHOLD;
    makeControlDecision(fieldId: string): Promise<AWDControlDecision>;
    executeIrrigation(fieldId: string, decision: AWDControlDecision): Promise<any>;
    getIrrigationStatus(fieldId: string): Promise<any>;
    stopIrrigation(fieldId: string, reason: string): Promise<any>;
    private enhanceIrrigationDecision;
    private getIrrigationRecommendation;
    private getActiveIrrigationId;
    private getActiveIrrigation;
    private getFieldSoilType;
    private getCurrentTemperature;
    private getCurrentHumidity;
    private getDaysSinceLastIrrigation;
    private getConcurrentIrrigations;
    private getCurrentSeason;
    private getFieldConfig;
    private getScheduleTemplate;
    private calculateCurrentWeek;
    private getCurrentPhase;
    private calculateNextPhaseDate;
    private evaluatePhaseRequirements;
    private updateFieldProgress;
    private getRainfallData;
    private evaluateWettingPhase;
    private evaluateDryingPhase;
}
export declare const awdControlServiceV2: AWDControlServiceV2;
//# sourceMappingURL=awd-control-v2.service.d.ts.map