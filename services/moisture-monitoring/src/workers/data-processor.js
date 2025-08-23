"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DataProcessor = void 0;
const logger_1 = require("../utils/logger");
class DataProcessor {
    constructor(cacheService, alertService, mqttService, websocketService) {
        this.cacheService = cacheService;
        this.alertService = alertService;
        this.mqttService = mqttService;
        this.websocketService = websocketService;
    }
    async start() {
        // Subscribe to moisture data from sensor ingestion service
        await this.cacheService.subscribe('sensor:moisture:data', async (data) => {
            try {
                await this.processMoistureData(data);
            }
            catch (error) {
                logger_1.logger.error({ error, data }, 'Failed to process moisture data');
            }
        });
        // Subscribe to MQTT data
        this.mqttService.subscribeSensorData(async (data) => {
            try {
                if (data.sensorType === 'moisture') {
                    await this.processMoistureData(data);
                }
            }
            catch (error) {
                logger_1.logger.error({ error, data }, 'Failed to process MQTT moisture data');
            }
        });
        logger_1.logger.info('Data processor started');
    }
    async processMoistureData(data) {
        // Transform data to MoistureReading format
        const reading = this.transformToMoistureReading(data);
        // Check for alerts
        const alerts = await this.alertService.checkAlerts(reading);
        // Publish to MQTT
        this.mqttService.publishMoistureReading(reading);
        // Emit via WebSocket
        this.websocketService.emitMoistureReading(reading);
        // Process alerts
        for (const alert of alerts) {
            this.mqttService.publishMoistureAlert(alert);
            this.websocketService.emitMoistureAlert(alert);
        }
        // Update cache with latest reading
        await this.cacheService.set(`moisture:latest:${reading.sensorId}`, reading, 300 // 5 minutes
        );
        // Invalidate analytics cache for this sensor
        await this.cacheService.invalidateSensorCache(reading.sensorId);
    }
    transformToMoistureReading(data) {
        // Handle different data formats from sensor ingestion
        if (data.gateway_id && data.sensor) {
            // M2M format
            const sensor = Array.isArray(data.sensor) ? data.sensor[0] : data.sensor;
            return {
                sensorId: `${data.gateway_id}-${sensor.sensor_id}`,
                timestamp: new Date(`${data.date} ${data.time}`),
                location: data.latitude && data.longitude ? {
                    lat: parseFloat(data.latitude),
                    lng: parseFloat(data.longitude),
                } : undefined,
                moistureSurfacePct: parseFloat(sensor.humid_hi),
                moistureDeepPct: parseFloat(sensor.humid_low),
                tempSurfaceC: parseFloat(sensor.temp_hi),
                tempDeepC: parseFloat(sensor.temp_low),
                ambientHumidityPct: parseFloat(sensor.amb_humid),
                ambientTempC: parseFloat(sensor.amb_temp),
                floodStatus: sensor.flood === 'yes',
                voltage: sensor.sensor_batt ? parseFloat(sensor.sensor_batt) / 100 : undefined,
                qualityScore: data.qualityScore,
            };
        }
        else if (data.sensorId && data.data) {
            // Pre-processed format
            return {
                sensorId: data.sensorId,
                timestamp: new Date(data.timestamp),
                location: data.location,
                moistureSurfacePct: data.data.moistureSurfacePct,
                moistureDeepPct: data.data.moistureDeepPct,
                tempSurfaceC: data.data.tempSurfaceC,
                tempDeepC: data.data.tempDeepC,
                ambientHumidityPct: data.data.ambientHumidityPct,
                ambientTempC: data.data.ambientTempC,
                floodStatus: data.data.floodStatus,
                voltage: data.data.voltage,
                qualityScore: data.qualityScore,
            };
        }
        else {
            throw new Error('Unknown data format');
        }
    }
}
exports.DataProcessor = DataProcessor;
//# sourceMappingURL=data-processor.js.map