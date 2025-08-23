"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.weatherIntegration = void 0;
const axios_1 = __importDefault(require("axios"));
const logger_1 = require("../utils/logger");
class WeatherIntegration {
    client;
    constructor() {
        const baseURL = process.env.WEATHER_SERVICE_URL || 'http://localhost:3007';
        this.client = axios_1.default.create({
            baseURL,
            timeout: 10000,
            headers: {
                'Content-Type': 'application/json',
            },
        });
        this.client.interceptors.request.use((config) => {
            logger_1.logger.debug({
                method: config.method,
                url: config.url,
                params: config.params,
            }, 'Outgoing request to weather service');
            return config;
        }, (error) => {
            logger_1.logger.error(error, 'Request error to weather service');
            return Promise.reject(error);
        });
    }
    async getCurrentRainfall(fieldId) {
        try {
            const response = await this.client.get(`/api/v1/rainfall/current`, {
                params: { field_id: fieldId }
            });
            if (response.data && response.data.data) {
                const data = response.data.data;
                return {
                    fieldId,
                    amount: data.rainfall_mm || 0,
                    timestamp: new Date(data.timestamp),
                    forecast: data.forecast || []
                };
            }
            return null;
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId }, 'Failed to get current rainfall');
            return null;
        }
    }
    async getRainfallHistory(fieldId, startDate, endDate) {
        try {
            const response = await this.client.get(`/api/v1/rainfall/history`, {
                params: {
                    field_id: fieldId,
                    start_date: startDate.toISOString(),
                    end_date: endDate.toISOString()
                }
            });
            if (response.data && response.data.data) {
                return response.data.data.map((item) => ({
                    fieldId,
                    amount: item.rainfall_mm || 0,
                    timestamp: new Date(item.timestamp)
                }));
            }
            return [];
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId }, 'Failed to get rainfall history');
            return [];
        }
    }
    async getRainfallForecast(fieldId, days = 7) {
        try {
            const response = await this.client.get(`/api/v1/rainfall/forecast`, {
                params: {
                    field_id: fieldId,
                    days
                }
            });
            if (response.data && response.data.data) {
                return response.data.data.map((item) => ({
                    date: new Date(item.date),
                    expectedAmount: item.expected_rainfall_mm || 0,
                    probability: item.probability || 0
                }));
            }
            return [];
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId }, 'Failed to get rainfall forecast');
            return [];
        }
    }
    async getCurrentWeather(fieldId) {
        try {
            const response = await this.client.get(`/api/v1/weather/current`, {
                params: { field_id: fieldId }
            });
            if (response.data && response.data.data) {
                const data = response.data.data;
                return {
                    fieldId,
                    temperature: data.temperature,
                    humidity: data.humidity,
                    rainfall: data.rainfall_mm || 0,
                    windSpeed: data.wind_speed || 0,
                    timestamp: new Date(data.timestamp)
                };
            }
            return null;
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId }, 'Failed to get current weather');
            return null;
        }
    }
    async healthCheck() {
        try {
            const response = await this.client.get('/health');
            return response.data.status === 'ok';
        }
        catch (error) {
            logger_1.logger.error(error, 'Weather service health check failed');
            return false;
        }
    }
}
exports.weatherIntegration = new WeatherIntegration();
//# sourceMappingURL=weather.integration.js.map