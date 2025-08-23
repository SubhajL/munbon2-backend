export interface WeatherReading {
    stationId: string;
    timestamp: Date;
    location?: {
        lat: number;
        lng: number;
    };
    temperature?: number;
    humidity?: number;
    pressure?: number;
    windSpeed?: number;
    windDirection?: number;
    rainfall?: number;
    solarRadiation?: number;
    uvIndex?: number;
    visibility?: number;
    cloudCover?: number;
    dewPoint?: number;
    feelsLike?: number;
    source: WeatherDataSource;
    qualityScore?: number;
}
export interface WeatherStation {
    stationId: string;
    name: string;
    type: StationType;
    location: {
        lat: number;
        lng: number;
        altitude?: number;
    };
    source: WeatherDataSource;
    isActive: boolean;
    lastReading?: WeatherReading;
    lastSeen: Date;
    metadata?: {
        installationDate?: Date;
        maintenanceSchedule?: string;
        equipment?: string[];
        [key: string]: any;
    };
}
export interface WeatherForecast {
    stationId?: string;
    location: {
        lat: number;
        lng: number;
    };
    timestamp: Date;
    forecastTime: Date;
    temperature: {
        min: number;
        max: number;
        avg: number;
    };
    humidity: {
        min: number;
        max: number;
        avg: number;
    };
    rainfall: {
        amount: number;
        probability: number;
    };
    windSpeed: number;
    windDirection: number;
    cloudCover: number;
    uvIndex: number;
    conditions: WeatherCondition;
    confidence: number;
    source: string;
}
export interface WeatherAlert {
    id?: string;
    type: WeatherAlertType;
    severity: AlertSeverity;
    title: string;
    message: string;
    affectedArea: {
        type: 'point' | 'region' | 'polygon';
        coordinates: any;
        radius?: number;
    };
    validFrom: Date;
    validUntil: Date;
    value?: number;
    threshold?: number;
    timestamp: Date;
    acknowledged: boolean;
    acknowledgedBy?: string;
    acknowledgedAt?: Date;
}
export interface WeatherAnalytics {
    location: {
        lat: number;
        lng: number;
    };
    period: string;
    startTime: Date;
    endTime: Date;
    stats: {
        temperature: {
            avg: number;
            min: number;
            max: number;
            stdDev: number;
        };
        humidity: {
            avg: number;
            min: number;
            max: number;
        };
        rainfall: {
            total: number;
            dailyAvg: number;
            maxDaily: number;
            rainDays: number;
        };
        windSpeed: {
            avg: number;
            max: number;
            prevailingDirection: number;
        };
        pressure: {
            avg: number;
            min: number;
            max: number;
        };
    };
    trends: {
        temperatureTrend: 'increasing' | 'decreasing' | 'stable';
        rainfallTrend: 'increasing' | 'decreasing' | 'stable';
        pressureTrend: 'increasing' | 'decreasing' | 'stable';
    };
    anomalies: {
        count: number;
        events: Array<{
            date: Date;
            type: string;
            value: number;
            deviation: number;
        }>;
    };
}
export interface IrrigationRecommendation {
    location: {
        lat: number;
        lng: number;
    };
    timestamp: Date;
    recommendation: 'irrigate' | 'postpone' | 'reduce' | 'maintain';
    confidence: number;
    reasoning: {
        currentSoilMoisture?: number;
        forecastedRainfall: number;
        evapotranspiration: number;
        temperature: number;
        windSpeed: number;
        humidity: number;
    };
    suggestedAmount?: number;
    suggestedTime?: Date;
    nextEvaluation: Date;
    cropType?: string;
    growthStage?: string;
}
export interface Evapotranspiration {
    location: {
        lat: number;
        lng: number;
    };
    timestamp: Date;
    et0: number;
    etc?: number;
    method: 'penman-monteith' | 'hargreaves' | 'blaney-criddle';
    inputs: {
        temperature: number;
        humidity: number;
        windSpeed: number;
        solarRadiation: number;
        pressure?: number;
    };
    cropCoefficient?: number;
}
export declare enum WeatherDataSource {
    TMD = "TMD",// Thai Meteorological Department
    AOS = "AOS",// Aeronautical Observation Station
    OPENWEATHER = "OPENWEATHER",
    CUSTOM = "CUSTOM",
    AGGREGATED = "AGGREGATED"
}
export declare enum StationType {
    SYNOPTIC = "SYNOPTIC",
    AUTOMATIC = "AUTOMATIC",
    AERONAUTICAL = "AERONAUTICAL",
    AGRICULTURAL = "AGRICULTURAL",
    RAIN_GAUGE = "RAIN_GAUGE"
}
export declare enum WeatherAlertType {
    EXTREME_HEAT = "EXTREME_HEAT",
    EXTREME_COLD = "EXTREME_COLD",
    HEAVY_RAIN = "HEAVY_RAIN",
    STRONG_WIND = "STRONG_WIND",
    FROST_WARNING = "FROST_WARNING",
    DROUGHT_WARNING = "DROUGHT_WARNING",
    STORM_WARNING = "STORM_WARNING",
    HAIL_WARNING = "HAIL_WARNING"
}
export declare enum AlertSeverity {
    INFO = "info",
    WARNING = "warning",
    CRITICAL = "critical"
}
export declare enum WeatherCondition {
    CLEAR = "clear",
    PARTLY_CLOUDY = "partly_cloudy",
    CLOUDY = "cloudy",
    OVERCAST = "overcast",
    LIGHT_RAIN = "light_rain",
    MODERATE_RAIN = "moderate_rain",
    HEAVY_RAIN = "heavy_rain",
    THUNDERSTORM = "thunderstorm",
    FOG = "fog",
    HAZE = "haze"
}
//# sourceMappingURL=weather.model.d.ts.map