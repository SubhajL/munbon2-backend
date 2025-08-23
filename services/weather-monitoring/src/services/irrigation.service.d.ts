import { DatabaseService } from './database.service';
import { AnalyticsService } from './analytics.service';
import { CacheService } from './cache.service';
import { IrrigationRecommendation } from '../models/weather.model';
export declare class IrrigationService {
    private databaseService;
    private analyticsService;
    private cacheService;
    private cropDatabase;
    constructor(databaseService: DatabaseService, analyticsService: AnalyticsService, cacheService: CacheService);
    private initializeCropDatabase;
    getIrrigationRecommendation(location: {
        lat: number;
        lng: number;
    }, cropType?: string, growthStage?: string, currentSoilMoisture?: number): Promise<IrrigationRecommendation>;
    getIrrigationSchedule(location: {
        lat: number;
        lng: number;
    }, cropType: string, growthStage: string, fieldSize: number, // hectares
    irrigationSystem?: 'drip' | 'sprinkler' | 'flood'): Promise<any>;
    getWaterBalanceAnalysis(location: {
        lat: number;
        lng: number;
    }, cropType: string, growthStage: string, period?: string): Promise<any>;
    private analyzeForecast;
    private generateRecommendation;
    private calculateIrrigationAmount;
    private calculateOptimalIrrigationTime;
    private calculateWaterRequirement;
    private generateIrrigationSchedule;
    private calculateDailyWaterBalance;
    private groupByDay;
    private estimateSoilMoisture;
    private calculateIrrigationEfficiency;
    private suggestAdjustments;
    private findConsecutiveDryDays;
    private checkExtendedDryPeriod;
    private getTimeRange;
    private getDefaultCropData;
    private isRecommendationValid;
}
//# sourceMappingURL=irrigation.service.d.ts.map