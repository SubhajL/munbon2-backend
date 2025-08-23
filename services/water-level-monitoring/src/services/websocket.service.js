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
            // Handle subscription to all water level data
            socket.on('subscribe:all', () => {
                socket.join('water-level:all');
                logger_1.logger.info({ socketId: socket.id }, 'Client subscribed to all water level data');
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
            // Handle subscription to gate recommendations
            socket.on('subscribe:gates', (gateIds) => {
                if (gateIds) {
                    gateIds.forEach(gateId => {
                        socket.join(`gate:${gateId}`);
                    });
                }
                else {
                    socket.join('gates:all');
                }
                logger_1.logger.info({ socketId: socket.id, gateIds }, 'Client subscribed to gate recommendations');
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
                service: 'water-level-monitoring',
                version: '1.0.0',
                timestamp: new Date(),
            });
        });
    }
    emitWaterLevelReading(reading) {
        // Emit to sensor-specific room
        this.io.to(`sensor:${reading.sensorId}`).emit('water-level:reading', {
            sensorId: reading.sensorId,
            timestamp: reading.timestamp,
            data: {
                level: reading.levelCm,
                voltage: reading.voltage,
                rssi: reading.rssi,
                temperature: reading.temperature,
            },
            location: reading.location,
            quality: reading.qualityScore,
        });
        // Emit to general room
        this.io.to('water-level:all').emit('water-level:reading', {
            sensorId: reading.sensorId,
            timestamp: reading.timestamp,
            level: reading.levelCm,
            location: reading.location,
        });
    }
    emitWaterLevelAlert(alert) {
        // Emit to severity-specific room
        this.io.to(`alerts:${alert.severity}`).emit('water-level:alert', alert);
        // Emit to all alerts room
        this.io.to('alerts:all').emit('water-level:alert', alert);
        // Emit to sensor-specific room
        this.io.to(`sensor:${alert.sensorId}`).emit('water-level:alert', alert);
    }
    emitAnalytics(sensorId, analytics) {
        this.io.to(`sensor:${sensorId}`).emit('water-level:analytics', {
            sensorId,
            analytics,
            timestamp: new Date(),
        });
    }
    emitGateRecommendation(gateId, recommendation) {
        this.io.to(`gate:${gateId}`).emit('gate:recommendation', recommendation);
        this.io.to('gates:all').emit('gate:recommendation', recommendation);
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