interface AWDMetrics {
    totalFields: number;
    activeIrrigations: number;
    waterSavedLiters: number;
    averageWaterLevel: number;
    sensorFailures: number;
    irrigationCycles: number;
}
declare class MetricsCollector {
    private redis;
    private metricsInterval;
    start(intervalMs?: number): void;
    stop(): void;
    private collectMetrics;
    private countTotalFields;
    private countActiveIrrigations;
    private calculateWaterSaved;
    private getAverageWaterLevel;
    private countSensorFailures;
    private countIrrigationCycles;
    getMetrics(): Promise<AWDMetrics | null>;
}
export declare const metricsCollector: MetricsCollector;
export declare const startMetricsCollection: () => void;
export {};
//# sourceMappingURL=metrics.d.ts.map