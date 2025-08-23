"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.WebSocketService = void 0;
const socket_io_1 = require("socket.io");
const redis_adapter_1 = require("@socket.io/redis-adapter");
const ioredis_1 = __importDefault(require("ioredis"));
const config_1 = require("../config");
const logger_1 = require("../utils/logger");
class WebSocketService {
    constructor(server) {
        this.io = new socket_io_1.Server(server, {
            path: config_1.config.websocket.path,
            cors: {
                origin: config_1.config.websocket.corsOrigin,
                methods: ['GET', 'POST'],
            },
        });
        // Setup Redis adapter for multi-instance support
        const pubClient = new ioredis_1.default({
            host: config_1.config.redis.host,
            port: config_1.config.redis.port,
            password: config_1.config.redis.password,
        });
        const subClient = pubClient.duplicate();
        this.io.adapter((0, redis_adapter_1.createAdapter)(pubClient, subClient));
        this.setupEventHandlers();
    }
    setupEventHandlers() {
        this.io.on('connection', (socket) => {
            logger_1.logger.info({ socketId: socket.id }, 'Client connected');
            // Handle subscription to sensor updates
            socket.on('subscribe:sensor', (sensorId) => {
                socket.join(`sensor:${sensorId}`);
                logger_1.logger.info({ socketId: socket.id, sensorId }, 'Client subscribed to sensor');
            });
            // Handle subscription to multiple sensors
            socket.on('subscribe:sensors', (sensorIds) => {
                sensorIds.forEach(sensorId => {
                    socket.join(`sensor:${sensorId}`);
                });
                logger_1.logger.info({ socketId: socket.id, count: sensorIds.length }, 'Client subscribed to multiple sensors');
            });
            // Handle subscription to all moisture data
            socket.on('subscribe:all', () => {
                socket.join('moisture:all');
                logger_1.logger.info({ socketId: socket.id }, 'Client subscribed to all moisture data');
            });
            // Handle subscription to alerts
            socket.on('subscribe:alerts', (severity) => {
                if (severity) {
                    socket.join(`alerts:${severity}`);
                }
                else {
                    socket.join('alerts:all');
                }
                logger_1.logger.info({ socketId: socket.id, severity }, 'Client subscribed to alerts');
            });
            // Handle unsubscription
            socket.on('unsubscribe:sensor', (sensorId) => {
                socket.leave(`sensor:${sensorId}`);
            });
            socket.on('unsubscribe:all', () => {
                socket.rooms.forEach(room => {
                    if (room !== socket.id) {
                        socket.leave(room);
                    }
                });
            });
            // Handle disconnection
            socket.on('disconnect', () => {
                logger_1.logger.info({ socketId: socket.id }, 'Client disconnected');
            });
            // Send initial connection acknowledgment
            socket.emit('connected', {
                service: 'moisture-monitoring',
                version: '1.0.0',
                timestamp: new Date(),
            });
        });
    }
    emitMoistureReading(reading) {
        // Emit to sensor-specific room
        this.io.to(`sensor:${reading.sensorId}`).emit('moisture:reading', {
            sensorId: reading.sensorId,
            timestamp: reading.timestamp,
            data: {
                surface: reading.moistureSurfacePct,
                deep: reading.moistureDeepPct,
                tempSurface: reading.tempSurfaceC,
                tempDeep: reading.tempDeepC,
                ambientHumidity: reading.ambientHumidityPct,
                ambientTemp: reading.ambientTempC,
                flood: reading.floodStatus,
            },
            location: reading.location,
            quality: reading.qualityScore,
        });
        // Emit to general room
        this.io.to('moisture:all').emit('moisture:reading', {
            sensorId: reading.sensorId,
            timestamp: reading.timestamp,
            surface: reading.moistureSurfacePct,
            deep: reading.moistureDeepPct,
            flood: reading.floodStatus,
        });
    }
    emitMoistureAlert(alert) {
        // Emit to severity-specific room
        this.io.to(`alerts:${alert.severity}`).emit('moisture:alert', alert);
        // Emit to all alerts room
        this.io.to('alerts:all').emit('moisture:alert', alert);
        // Emit to sensor-specific room
        this.io.to(`sensor:${alert.sensorId}`).emit('moisture:alert', alert);
    }
    emitAnalytics(sensorId, analytics) {
        this.io.to(`sensor:${sensorId}`).emit('moisture:analytics', {
            sensorId,
            analytics,
            timestamp: new Date(),
        });
    }
    emitSystemStatus(status) {
        this.io.emit('system:status', status);
    }
    getConnectedClients() {
        return this.io.sockets.sockets.size;
    }
    close() {
        this.io.close();
    }
}
exports.WebSocketService = WebSocketService;
//# sourceMappingURL=websocket.service.js.map