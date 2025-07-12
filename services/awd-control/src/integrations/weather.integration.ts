import axios, { AxiosInstance } from 'axios';
import { logger } from '../utils/logger';
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

class WeatherIntegration {
  private client: AxiosInstance;

  constructor() {
    const baseURL = process.env.WEATHER_SERVICE_URL || 'http://localhost:3007';
    
    this.client = axios.create({
      baseURL,
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor
    this.client.interceptors.request.use(
      (config) => {
        logger.debug({
          method: config.method,
          url: config.url,
          params: config.params,
        }, 'Outgoing request to weather service');
        return config;
      },
      (error) => {
        logger.error(error, 'Request error to weather service');
        return Promise.reject(error);
      }
    );
  }

  /**
   * Get current rainfall data for a field
   */
  async getCurrentRainfall(fieldId: string): Promise<RainfallData | null> {
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
    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to get current rainfall');
      return null;
    }
  }

  /**
   * Get rainfall history for a field
   */
  async getRainfallHistory(
    fieldId: string,
    startDate: Date,
    endDate: Date
  ): Promise<RainfallData[]> {
    try {
      const response = await this.client.get(`/api/v1/rainfall/history`, {
        params: {
          field_id: fieldId,
          start_date: startDate.toISOString(),
          end_date: endDate.toISOString()
        }
      });

      if (response.data && response.data.data) {
        return response.data.data.map((item: any) => ({
          fieldId,
          amount: item.rainfall_mm || 0,
          timestamp: new Date(item.timestamp)
        }));
      }

      return [];
    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to get rainfall history');
      return [];
    }
  }

  /**
   * Get rainfall forecast for a field
   */
  async getRainfallForecast(fieldId: string, days: number = 7): Promise<RainfallForecast[]> {
    try {
      const response = await this.client.get(`/api/v1/rainfall/forecast`, {
        params: {
          field_id: fieldId,
          days
        }
      });

      if (response.data && response.data.data) {
        return response.data.data.map((item: any) => ({
          date: new Date(item.date),
          expectedAmount: item.expected_rainfall_mm || 0,
          probability: item.probability || 0
        }));
      }

      return [];
    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to get rainfall forecast');
      return [];
    }
  }

  /**
   * Get current weather data
   */
  async getCurrentWeather(fieldId: string): Promise<WeatherData | null> {
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
    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to get current weather');
      return null;
    }
  }

  /**
   * Health check for weather service
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await this.client.get('/health');
      return response.data.status === 'ok';
    } catch (error) {
      logger.error(error, 'Weather service health check failed');
      return false;
    }
  }
}

export const weatherIntegration = new WeatherIntegration();