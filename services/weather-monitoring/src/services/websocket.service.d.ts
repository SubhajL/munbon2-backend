import { Server as HttpServer } from 'http';
import { WeatherReading, WeatherAlert, WeatherForecast } from '../models/weather.model';
export declare class WebSocketService {
    private io;
    private connections;
    private subscriptions;
    constructor(server: HttpServer);
    private setupMiddleware;
    private setupEventHandlers;
    private handleWeatherSubscription;
    private handleAlertSubscription;
    private handleForecastSubscription;
    private handleAnalyticsSubscription;
    private handleIrrigationSubscription;
    private handleUnsubscribe;
    private handleCurrentQuery;
    private handleStationsQuery;
    private handleDisconnect;
    private createSubscriptionKey;
    broadcastWeatherUpdate(reading: WeatherReading): void;
    broadcastAlert(alert: WeatherAlert): void;
    broadcastForecast(location: {
        lat: number;
        lng: number;
    }, forecast: WeatherForecast[]): void;
    broadcastAnalytics(location: {
        lat: number;
        lng: number;
    }, analytics: any): void;
    broadcastIrrigationRecommendation(recommendation: any): void;
    getConnectionCount(): number;
    getSubscriptionCount(): number;
    getDetailedStats(): any;
}
//# sourceMappingURL=websocket.service.d.ts.map