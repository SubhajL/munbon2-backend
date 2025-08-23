"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DataProcessor = void 0;
const logger_1 = require("../utils/logger");
class DataProcessor {
    constructor(cacheService, alertService, mqttService, websocketService, gateControlService) {
        this.cacheService = cacheService;
        this.alertService = alertService;
        this.mqttService = mqttService;
        this.websocketService = websocketService;
        this.gateControlService = gateControlService;
    }
    async start() {
        // Subscribe to water level data from sensor ingestion service
        await this.cacheService.subscribe('sensor:water-level:data', async (data) => {
            try {
                await this.processWaterLevelData(data);
            }
            catch (error) {
                logger_1.logger.error({ error, data }, 'Failed to process water level data');
            }
        });
        // Subscribe to MQTT data
        this.mqttService.subscribeSensorData(async (data) => {
            try {
                if (data.sensorType === 'water-level') {
                    await this.processWaterLevelData(data);
                }
            }
            catch (error) {
                logger_1.logger.error({ error, data }, 'Failed to process MQTT water level data');
            }
        });
        // Subscribe to gate commands
        this.mqttService.subscribeGateCommands(async (data) => {
            try {
                await this.processGateCommand(data);
            }
            catch (error) {
                logger_1.logger.error({ error, data }, 'Failed to process gate command');
            }
        });
        logger_1.logger.info('Data processor started');
    }
    async processWaterLevelData(data) {
        // Transform data to WaterLevelReading format
        const reading = this.transformToWaterLevelReading(data);
        // Check for alerts
        const alerts = await this.alertService.checkAlerts(reading);
        // Publish to MQTT
        this.mqttService.publishWaterLevelReading(reading);
        // Emit via WebSocket
        this.websocketService.emitWaterLevelReading(reading);
        // Process alerts
        for (const alert of alerts) {
            this.mqttService.publishWaterLevelAlert(alert);
            this.websocketService.emitWaterLevelAlert(alert);
        }
        // Update cache with latest reading
        await this.cacheService.set(`water-level:latest:${reading.sensorId}`, reading, 300 // 5 minutes
        );
        // Invalidate analytics cache for this sensor
        await this.cacheService.invalidateSensorCache(reading.sensorId);
        // Check if gate control is needed
        if (data.gateId) {
            const recommendation = await this.gateControlService.generateRecommendation(data.gateId, reading.sensorId, reading);
            if (recommendation) {
                this.mqttService.publishGateRecommendation(data.gateId, recommendation);
                this.websocketService.emitGateRecommendation(data.gateId, recommendation);
            }
        }
    }
    transformToWaterLevelReading(data) {
        // Handle different data formats from sensor ingestion
        if (data.deviceID && data.level !== undefined) {
            // RID-R format
            return {
                sensorId: data.deviceID,
                timestamp: new Date(data.timestamp || Date.now()),
                location: data.latitude && data.longitude ? {
                    lat: data.latitude,
                    lng: data.longitude,
                } : undefined,
                levelCm: data.level,
                voltage: data.voltage ? data.voltage / 100 : undefined,
                rssi: data.RSSI,
                temperature: data.temperature,
                qualityScore: data.qualityScore,
            };
        }
        else if (data.sensorId && data.data) {
            // Pre-processed format
            return {
                sensorId: data.sensorId,
                timestamp: new Date(data.timestamp),
                location: data.location,
                levelCm: data.data.levelCm,
                voltage: data.data.voltage,
                rssi: data.data.rssi,
                temperature: data.data.temperature,
                qualityScore: data.qualityScore,
            };
        }
        else {
            throw new Error('Unknown data format');
        }
    }
    async processGateCommand(data) {
        logger_1.logger.info({ data }, 'Processing gate command');
        // In a real implementation, this would coordinate with the SCADA service
        // For now, just log and emit status
        this.websocketService.emitSystemStatus({
            type: 'gate_command_received',
            gateId: data.gateId,
            command: data.command,
            timestamp: new Date(),
        });
    }
}
exports.DataProcessor = DataProcessor;
//# sourceMappingURL=data-processor.js.map