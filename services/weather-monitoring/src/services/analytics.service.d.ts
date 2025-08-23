import { DatabaseService } from './database.service';
import { CacheService } from './cache.service';
import { WeatherAnalytics, Evapotranspiration } from '../models/weather.model';
export declare class AnalyticsService {
    private databaseService;
    private cacheService;
    constructor(databaseService: DatabaseService, cacheService: CacheService);
    getWeatherAnalytics(location: {
        lat: number;
        lng: number;
    }, period?: string): Promise<WeatherAnalytics>;
    getComparativeAnalytics(locations: Array<{
        lat: number;
        lng: number;
    }>, period?: string): Promise<any>;
    calculateEvapotranspiration(location: {
        lat: number;
        lng: number;
    }, date?: Date, cropCoefficient?: number): Promise<Evapotranspiration>;
    getWeatherTrends(location: {
        lat: number;
        lng: number;
    }, metric: 'temperature' | 'rainfall' | 'humidity' | 'pressure', period?: string): Promise<any>;
    detectAnomalies(location: {
        lat: number;
        lng: number;
    }, threshold?: number): Promise<any>;
    private calculateAnalytics;
    private calculatePenmanMonteith;
    private getTimeRange;
    private getAggregationInterval;
    private average;
    private standardDeviation;
    private calculatePrevailingDirection;
    private aggregateDaily;
    private calculateSimpleTrend;
    private calculateTrend;
    private calculateMovingAverage;
    private detectSimpleAnomalies;
    private calculateBaseline;
    private findExtreme;
    private findMostStable;
}
//# sourceMappingURL=analytics.service.d.ts.map