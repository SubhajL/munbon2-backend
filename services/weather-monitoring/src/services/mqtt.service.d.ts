import { EventEmitter } from 'events';
import { WeatherReading, WeatherAlert } from '../models/weather.model';
export declare class MqttService extends EventEmitter {
    private client;
    private connected;
    private reconnectAttempts;
    private readonly maxReconnectAttempts;
    constructor();
    connect(): Promise<void>;
    private subscribeToTopics;
    private handleMessage;
    private handleCommand;
    private handleRequest;
    private handleSensorData;
    publishWeatherData(reading: WeatherReading): Promise<void>;
    publishWeatherAlert(alert: WeatherAlert): Promise<void>;
    publishForecast(location: {
        lat: number;
        lng: number;
    }, forecast: any): Promise<void>;
    publishAnalytics(location: {
        lat: number;
        lng: number;
    }, analytics: any): Promise<void>;
    publishIrrigationRecommendation(recommendation: any): Promise<void>;
    private publishStatus;
    disconnect(): Promise<void>;
    isConnected(): boolean;
}
//# sourceMappingURL=mqtt.service.d.ts.map