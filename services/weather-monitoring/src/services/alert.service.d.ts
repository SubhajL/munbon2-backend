import { CacheService } from './cache.service';
import { WeatherReading, WeatherAlert } from '../models/weather.model';
export declare class AlertService {
    private cacheService;
    private alertCooldowns;
    constructor(cacheService: CacheService);
    checkWeatherAlerts(reading: WeatherReading): Promise<WeatherAlert[]>;
    checkForecastAlerts(forecasts: any[]): Promise<WeatherAlert[]>;
    private createAlert;
    private sendNotification;
    private sendToAlertService;
    acknowledgeAlert(alertId: string, acknowledgedBy: string): Promise<void>;
    getActiveAlerts(location?: {
        lat: number;
        lng: number;
    }, radius?: number): Promise<WeatherAlert[]>;
}
//# sourceMappingURL=alert.service.d.ts.map