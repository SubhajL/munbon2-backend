import { RainfallData } from '../types/awd-control.types';
export interface WeatherData {
    fieldId: string;
    temperature: number;
    humidity: number;
    rainfall: number;
    windSpeed: number;
    timestamp: Date;
}
export interface RainfallForecast {
    date: Date;
    expectedAmount: number;
    probability: number;
}
declare class WeatherIntegration {
    private client;
    constructor();
    getCurrentRainfall(fieldId: string): Promise<RainfallData | null>;
    getRainfallHistory(fieldId: string, startDate: Date, endDate: Date): Promise<RainfallData[]>;
    getRainfallForecast(fieldId: string, days?: number): Promise<RainfallForecast[]>;
    getCurrentWeather(fieldId: string): Promise<WeatherData | null>;
    healthCheck(): Promise<boolean>;
}
export declare const weatherIntegration: WeatherIntegration;
export {};
//# sourceMappingURL=weather.integration.d.ts.map