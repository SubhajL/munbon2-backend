"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DataProcessor = void 0;
const logger_1 = require("../utils/logger");
class DataProcessor {
    constructor(cacheService, databaseService, alertService, mqttService, websocketService) {
        this.cacheService = cacheService;
        this.databaseService = databaseService;
        this.alertService = alertService;
        this.mqttService = mqttService;
        this.websocketService = websocketService;
        this.processInterval = null;
    }
    start() {
        logger_1.logger.info('Starting weather data processor');
        // Process incoming data every 30 seconds
        this.processInterval = setInterval(() => {
            this.processQueuedData().catch(err => {
                logger_1.logger.error({ err }, 'Error processing weather data');
            });
        }, 30000);
        // Subscribe to real-time data updates
        this.subscribeToDataUpdates();
    }
    stop() {
        if (this.processInterval) {
            clearInterval(this.processInterval);
            this.processInterval = null;
        }
        logger_1.logger.info('Stopped weather data processor');
    }
    subscribeToDataUpdates() {
        // Subscribe to Redis channel for real-time updates
        this.cacheService.subscribe('weather:data:new', async (data) => {
            try {
                await this.processWeatherData(data);
            }
            catch (error) {
                logger_1.logger.error({ error, data }, 'Failed to process real-time weather data');
            }
        });
        // Subscribe to MQTT sensor data
        this.mqttService.on('sensor-data', async ({ stationId, data }) => {
            try {
                const reading = {
                    stationId,
                    timestamp: new Date(data.timestamp || Date.now()),
                    temperature: data.temperature,
                    humidity: data.humidity,
                    pressure: data.pressure,
                    windSpeed: data.windSpeed,
                    windDirection: data.windDirection,
                    rainfall: data.rainfall,
                    solarRadiation: data.solarRadiation,
                    uvIndex: data.uvIndex,
                    visibility: data.visibility,
                    cloudCover: data.cloudCover,
                    dewPoint: data.dewPoint,
                    feelsLike: data.feelsLike,
                    source: data.source || 'CUSTOM',
                    location: data.location,
                    qualityScore: data.qualityScore,
                };
                await this.processWeatherData(reading);
            }
            catch (error) {
                logger_1.logger.error({ error, stationId }, 'Failed to process MQTT sensor data');
            }
        });
    }
    async processQueuedData() {
        // This method would process any queued data from a message queue
        // For now, it's a placeholder for batch processing logic
        logger_1.logger.debug('Processing queued weather data');
    }
    async processWeatherData(reading) {
        logger_1.logger.debug({ stationId: reading.stationId }, 'Processing weather reading');
        // Validate data quality
        const qualityScore = this.validateDataQuality(reading);
        reading.qualityScore = qualityScore;
        if (qualityScore < 0.5) {
            logger_1.logger.warn({
                stationId: reading.stationId,
                qualityScore
            }, 'Low quality weather data received');
        }
        // Check for alerts
        const alerts = await this.alertService.checkWeatherAlerts(reading);
        // Broadcast alerts
        for (const alert of alerts) {
            await this.mqttService.publishWeatherAlert(alert);
            this.websocketService.broadcastAlert(alert);
        }
        // Cache current reading
        const cacheKey = `weather:current:${reading.stationId}`;
        await this.cacheService.set(cacheKey, reading, 300); // Cache for 5 minutes
        // Update location-based cache
        if (reading.location) {
            const locationKey = `weather:location:${reading.location.lat}:${reading.location.lng}`;
            await this.cacheService.set(locationKey, reading, 300);
        }
        // Broadcast updates
        await this.broadcastUpdates(reading);
        // Log metrics
        this.logMetrics(reading);
    }
    validateDataQuality(reading) {
        let score = 1.0;
        const issues = [];
        // Check temperature range
        if (reading.temperature !== undefined) {
            if (reading.temperature < -50 || reading.temperature > 60) {
                score -= 0.3;
                issues.push('Temperature out of range');
            }
        }
        else {
            score -= 0.1;
        }
        // Check humidity range
        if (reading.humidity !== undefined) {
            if (reading.humidity < 0 || reading.humidity > 100) {
                score -= 0.3;
                issues.push('Humidity out of range');
            }
        }
        else {
            score -= 0.1;
        }
        // Check pressure range
        if (reading.pressure !== undefined) {
            if (reading.pressure < 870 || reading.pressure > 1080) {
                score -= 0.2;
                issues.push('Pressure out of range');
            }
        }
        // Check wind speed
        if (reading.windSpeed !== undefined) {
            if (reading.windSpeed < 0 || reading.windSpeed > 200) {
                score -= 0.2;
                issues.push('Wind speed out of range');
            }
        }
        // Check data freshness
        const age = Date.now() - reading.timestamp.getTime();
        if (age > 3600000) { // Older than 1 hour
            score -= 0.2;
            issues.push('Stale data');
        }
        if (issues.length > 0) {
            logger_1.logger.debug({
                stationId: reading.stationId,
                issues,
                score
            }, 'Data quality issues detected');
        }
        return Math.max(0, score);
    }
    async broadcastUpdates(reading) {
        // Publish to MQTT
        await this.mqttService.publishWeatherData(reading);
        // Broadcast via WebSocket
        this.websocketService.broadcastWeatherUpdate(reading);
        // Publish to Redis for other services
        await this.cacheService.publish('weather:updates', {
            type: 'reading',
            data: reading,
            timestamp: new Date(),
        });
    }
    logMetrics(reading) {
        // Log metrics for monitoring
        const metrics = {
            station: reading.stationId,
            source: reading.source,
            hasTemperature: reading.temperature !== undefined,
            hasHumidity: reading.humidity !== undefined,
            hasRainfall: reading.rainfall !== undefined,
            qualityScore: reading.qualityScore,
            timestamp: reading.timestamp.toISOString(),
        };
        logger_1.logger.info({ metrics }, 'Weather reading processed');
    }
}
exports.DataProcessor = DataProcessor;
//# sourceMappingURL=data-processor.js.map