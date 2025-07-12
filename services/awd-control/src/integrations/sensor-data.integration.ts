import axios, { AxiosInstance } from 'axios';
import { logger } from '../utils/logger';

export interface SensorDataQuery {
  fieldId?: string;
  sensorId?: string;
  startDate?: Date;
  endDate?: Date;
  limit?: number;
}

export interface SensorRegistration {
  sensorId: string;
  fieldId: string;
  type: 'water_level' | 'moisture';
  macAddress?: string;
  metadata?: any;
}

class SensorDataIntegration {
  private client: AxiosInstance;

  constructor() {
    const baseURL = process.env.SENSOR_DATA_URL || 'http://localhost:3003';
    
    this.client = axios.create({
      baseURL,
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor for logging
    this.client.interceptors.request.use(
      (config) => {
        logger.debug({
          method: config.method,
          url: config.url,
          params: config.params,
        }, 'Outgoing request to sensor-data service');
        return config;
      },
      (error) => {
        logger.error(error, 'Request error to sensor-data service');
        return Promise.reject(error);
      }
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        logger.error({
          status: error.response?.status,
          data: error.response?.data,
          url: error.config?.url,
        }, 'Response error from sensor-data service');
        return Promise.reject(error);
      }
    );
  }

  /**
   * Get water level readings from sensor-data service
   */
  async getWaterLevelReadings(query: SensorDataQuery): Promise<any> {
    try {
      const response = await this.client.get('/api/v1/water-level', {
        params: {
          field_id: query.fieldId,
          sensor_id: query.sensorId,
          start_date: query.startDate?.toISOString(),
          end_date: query.endDate?.toISOString(),
          limit: query.limit,
        },
      });

      return response.data;
    } catch (error) {
      logger.error({ error, query }, 'Failed to get water level readings');
      throw error;
    }
  }

  /**
   * Get moisture readings from sensor-data service
   */
  async getMoistureReadings(query: SensorDataQuery): Promise<any> {
    try {
      const response = await this.client.get('/api/v1/moisture', {
        params: {
          field_id: query.fieldId,
          sensor_id: query.sensorId,
          start_date: query.startDate?.toISOString(),
          end_date: query.endDate?.toISOString(),
          limit: query.limit,
        },
      });

      return response.data;
    } catch (error) {
      logger.error({ error, query }, 'Failed to get moisture readings');
      throw error;
    }
  }

  /**
   * Register a sensor with the sensor-data service
   */
  async registerSensor(registration: SensorRegistration): Promise<any> {
    try {
      const response = await this.client.post('/api/v1/sensors/register', {
        sensor_id: registration.sensorId,
        field_id: registration.fieldId,
        type: registration.type,
        mac_address: registration.macAddress,
        metadata: registration.metadata,
      });

      logger.info({
        sensorId: registration.sensorId,
        fieldId: registration.fieldId,
        type: registration.type,
      }, 'Sensor registered successfully');

      return response.data;
    } catch (error) {
      logger.error({ error, registration }, 'Failed to register sensor');
      throw error;
    }
  }

  /**
   * Get sensor status from sensor-data service
   */
  async getSensorStatus(sensorId: string): Promise<any> {
    try {
      const response = await this.client.get(`/api/v1/sensors/${sensorId}/status`);
      return response.data;
    } catch (error) {
      logger.error({ error, sensorId }, 'Failed to get sensor status');
      throw error;
    }
  }

  /**
   * Subscribe to real-time sensor updates (WebSocket)
   */
  subscribeToSensorUpdates(fieldId: string, _callback: (data: any) => void): void {
    // This would typically use WebSocket or Server-Sent Events
    // For now, we'll use Kafka consumer in the main service
    logger.info({ fieldId }, 'Sensor update subscription requested');
  }

  /**
   * Health check for sensor-data service
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await this.client.get('/health');
      return response.data.status === 'ok';
    } catch (error) {
      logger.error(error, 'Sensor-data service health check failed');
      return false;
    }
  }
}

export const sensorDataIntegration = new SensorDataIntegration();