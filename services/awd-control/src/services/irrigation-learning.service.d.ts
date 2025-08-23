export interface IrrigationPrediction {
    fieldId: string;
    conditions: {
        initialLevel: number;
        targetLevel: number;
        soilType: string;
        temperature: number;
        humidity: number;
        lastIrrigationDays: number;
        concurrentIrrigations: number;
        season: string;
    };
    predictions: {
        estimatedDuration: number;
        expectedFlowRate: number;
        waterVolume: number;
        confidenceLevel: number;
        confidenceIntervalLower: number;
        confidenceIntervalUpper: number;
    };
    modelVersion: string;
    basedOnSamples: number;
}
export interface PerformancePattern {
    fieldId: string;
    pattern: string;
    description: string;
    frequency: number;
    impact: 'positive' | 'negative' | 'neutral';
    recommendations: string[];
}
export declare class IrrigationLearningService {
    private postgresPool;
    private readonly MODEL_VERSION;
    private readonly MIN_SAMPLES_FOR_PREDICTION;
    private readonly RECENT_DAYS_WEIGHT;
    private readonly SEASONAL_ADJUSTMENT;
    predictIrrigationPerformance(fieldId: string, conditions: IrrigationPrediction['conditions']): Promise<IrrigationPrediction>;
    analyzeFieldPatterns(fieldId: string): Promise<PerformancePattern[]>;
    updateModelWithResults(scheduleId: string): Promise<void>;
    getOptimalParameters(fieldId: string): Promise<{
        sensorCheckInterval: number;
        minFlowRateThreshold: number;
        maxDurationMinutes: number;
        toleranceCm: number;
    }>;
    private getHistoricalPerformance;
    private calculateWeightedPredictions;
    private getDefaultPrediction;
    private getDefaultValues;
    private storePrediction;
    private extractFeatures;
    private updateFieldModel;
    private updateGlobalModel;
    private calculateOptimalCheckInterval;
    private analyzeFlowRatePattern;
    private analyzeTimeOfDayPattern;
    private analyzeAnomalyPattern;
    private analyzeEfficiencyTrend;
    private getAnomalyRecommendations;
}
export declare const irrigationLearningService: IrrigationLearningService;
//# sourceMappingURL=irrigation-learning.service.d.ts.map