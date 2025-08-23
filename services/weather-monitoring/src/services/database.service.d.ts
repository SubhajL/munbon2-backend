import { WeatherReading, WeatherStation, WeatherForecast } from '../models/weather.model';
export declare class DatabaseService {
    private timescalePool;
    private postgresPool;
    constructor();
    getCurrentWeather(location?: {
        lat: number;
        lng: number;
    }, stationIds?: string[]): Promise<WeatherReading[]>;
    getHistoricalWeather(startTime: Date, endTime: Date, location?: {
        lat: number;
        lng: number;
    }, stationIds?: string[]): Promise<WeatherReading[]>;
    getAggregatedWeather(startTime: Date, endTime: Date, interval: string, location?: {
        lat: number;
        lng: number;
    }, stationId?: string): Promise<any[]>;
    getWeatherStations(active?: boolean): Promise<WeatherStation[]>;
    getWeatherForecasts(location: {
        lat: number;
        lng: number;
    }, days?: number): Promise<WeatherForecast[]>;
    private mapToWeatherReadings;
    private mapToWeatherStations;
    private mapToWeatherForecasts;
    close(): Promise<void>;
}
//# sourceMappingURL=database.service.d.ts.map