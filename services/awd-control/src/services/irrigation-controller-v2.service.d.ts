export interface IrrigationConfig {
    fieldId: string;
    targetLevelCm: number;
    toleranceCm: number;
    maxDurationMinutes: number;
    sensorCheckIntervalSeconds: number;
    minFlowRateCmPerMin: number;
    emergencyStopLevel: number;
    targetFlowRate?: number;
}
export interface IrrigationStatus {
    scheduleId: string;
    fieldId: string;
    status: 'preparing' | 'active' | 'completed' | 'failed' | 'cancelled';
    startTime: Date;
    currentLevelCm: number;
    targetLevelCm: number;
    flowRateCmPerMin: number;
    estimatedCompletionTime?: Date;
    anomaliesDetected: number;
}
export interface AnomalyDetection {
    type: 'low_flow' | 'no_rise' | 'rapid_drop' | 'sensor_failure' | 'overflow_risk';
    severity: 'warning' | 'critical';
    description: string;
    metrics: any;
}
export declare class IrrigationControllerV2Service {
    private postgresPool;
    private timescalePool;
    private redis;
    private readonly DEFAULT_TOLERANCE_CM;
    private readonly DEFAULT_CHECK_INTERVAL_SEC;
    private readonly DEFAULT_MAX_DURATION_MIN;
    private readonly MIN_FLOW_RATE_CM_PER_MIN;
    private readonly NO_RISE_THRESHOLD_CHECKS;
    private readonly RAPID_DROP_THRESHOLD_CM;
    private activeIrrigations;
    startIrrigation(config: IrrigationConfig): Promise<IrrigationStatus>;
    private startMonitoring;
    private calculateRequiredFlowRate;
    private getPercolationRate;
    private storeCanalLevels;
    private detectAnomalies;
    private handleAnomaly;
    private completeIrrigation;
    stopIrrigation(scheduleId: string, reason: string): Promise<void>;
    private estimateCompletionTime;
    private getCurrentWaterLevel;
    private createIrrigationSchedule;
    private updateIrrigationSchedule;
    private recordMonitoringData;
    private recordAnomaly;
    private recordPerformanceMetrics;
    private updateLearningModel;
    private getIrrigationStatus;
    private updateIrrigationStatus;
    private getActiveIrrigation;
    private getStartTime;
    private handleSensorFailure;
    private handleMonitoringError;
    private switchToBackupSensor;
}
export declare const irrigationControllerV2Service: IrrigationControllerV2Service;
//# sourceMappingURL=irrigation-controller-v2.service.d.ts.map