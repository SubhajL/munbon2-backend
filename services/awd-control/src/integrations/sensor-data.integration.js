"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.sensorDataIntegration = void 0;
const axios_1 = __importDefault(require("axios"));
const logger_1 = require("../utils/logger");
class SensorDataIntegration {
    client;
    constructor() {
        const baseURL = process.env.SENSOR_DATA_URL || 'http://localhost:3003';
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
            }, 'Outgoing request to sensor-data service');
            return config;
        }, (error) => {
            logger_1.logger.error(error, 'Request error to sensor-data service');
            return Promise.reject(error);
        });
        this.client.interceptors.response.use((response) => response, (error) => {
            logger_1.logger.error({
                status: error.response?.status,
                data: error.response?.data,
                url: error.config?.url,
            }, 'Response error from sensor-data service');
            return Promise.reject(error);
        });
    }
    async getWaterLevelReadings(query) {
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
        }
        catch (error) {
            logger_1.logger.error({ error, query }, 'Failed to get water level readings');
            throw error;
        }
    }
    async getMoistureReadings(query) {
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
        }
        catch (error) {
            logger_1.logger.error({ error, query }, 'Failed to get moisture readings');
            throw error;
        }
    }
    async registerSensor(registration) {
        try {
            const response = await this.client.post('/api/v1/sensors/register', {
                sensor_id: registration.sensorId,
                field_id: registration.fieldId,
                type: registration.type,
                mac_address: registration.macAddress,
                metadata: registration.metadata,
            });
            logger_1.logger.info({
                sensorId: registration.sensorId,
                fieldId: registration.fieldId,
                type: registration.type,
            }, 'Sensor registered successfully');
            return response.data;
        }
        catch (error) {
            logger_1.logger.error({ error, registration }, 'Failed to register sensor');
            throw error;
        }
    }
    async getSensorStatus(sensorId) {
        try {
            const response = await this.client.get(`/api/v1/sensors/${sensorId}/status`);
            return response.data;
        }
        catch (error) {
            logger_1.logger.error({ error, sensorId }, 'Failed to get sensor status');
            throw error;
        }
    }
    subscribeToSensorUpdates(fieldId, _callback) {
        logger_1.logger.info({ fieldId }, 'Sensor update subscription requested');
    }
    async healthCheck() {
        try {
            const response = await this.client.get('/health');
            return response.data.status === 'ok';
        }
        catch (error) {
            logger_1.logger.error(error, 'Sensor-data service health check failed');
            return false;
        }
    }
}
exports.sensorDataIntegration = new SensorDataIntegration();
//# sourceMappingURL=sensor-data.integration.js.map