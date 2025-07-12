import { Server as SocketServer, Socket } from 'socket.io';
import { createAdapter } from '@socket.io/redis-adapter';
import Redis from 'ioredis';
import { config } from '../config';
import { logger } from '../utils/logger';
import { WaterLevelReading, WaterLevelAlert } from '../models/water-level.model';

export class WebSocketService {
  private io: SocketServer;

  constructor(server: any) {
    this.io = new SocketServer(server, {
      path: config.websocket.path,
      cors: {
        origin: config.websocket.corsOrigin,
        methods: ['GET', 'POST'],
      },
    });
    
    // Setup Redis adapter for multi-instance support
    const pubClient = new Redis({
      host: config.redis.host,
      port: config.redis.port,
      password: config.redis.password,
    });
    const subClient = pubClient.duplicate();
    
    this.io.adapter(createAdapter(pubClient, subClient));
    
    this.setupEventHandlers();
  }

  private setupEventHandlers(): void {
    this.io.on('connection', (socket: Socket) => {
      logger.info({ socketId: socket.id }, 'Client connected');
      
      // Handle subscription to sensor updates
      socket.on('subscribe:sensor', (sensorId: string) => {
        socket.join(`sensor:${sensorId}`);
        logger.info({ socketId: socket.id, sensorId }, 'Client subscribed to sensor');
      });
      
      // Handle subscription to multiple sensors
      socket.on('subscribe:sensors', (sensorIds: string[]) => {
        sensorIds.forEach(sensorId => {
          socket.join(`sensor:${sensorId}`);
        });
        logger.info({ socketId: socket.id, count: sensorIds.length }, 'Client subscribed to multiple sensors');
      });
      
      // Handle subscription to all water level data
      socket.on('subscribe:all', () => {
        socket.join('water-level:all');
        logger.info({ socketId: socket.id }, 'Client subscribed to all water level data');
      });
      
      // Handle subscription to alerts
      socket.on('subscribe:alerts', (severity?: string) => {
        if (severity) {
          socket.join(`alerts:${severity}`);
        } else {
          socket.join('alerts:all');
        }
        logger.info({ socketId: socket.id, severity }, 'Client subscribed to alerts');
      });
      
      // Handle subscription to gate recommendations
      socket.on('subscribe:gates', (gateIds?: string[]) => {
        if (gateIds) {
          gateIds.forEach(gateId => {
            socket.join(`gate:${gateId}`);
          });
        } else {
          socket.join('gates:all');
        }
        logger.info({ socketId: socket.id, gateIds }, 'Client subscribed to gate recommendations');
      });
      
      // Handle unsubscription
      socket.on('unsubscribe:sensor', (sensorId: string) => {
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
        logger.info({ socketId: socket.id }, 'Client disconnected');
      });
      
      // Send initial connection acknowledgment
      socket.emit('connected', {
        service: 'water-level-monitoring',
        version: '1.0.0',
        timestamp: new Date(),
      });
    });
  }

  emitWaterLevelReading(reading: WaterLevelReading): void {
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

  emitWaterLevelAlert(alert: WaterLevelAlert): void {
    // Emit to severity-specific room
    this.io.to(`alerts:${alert.severity}`).emit('water-level:alert', alert);
    
    // Emit to all alerts room
    this.io.to('alerts:all').emit('water-level:alert', alert);
    
    // Emit to sensor-specific room
    this.io.to(`sensor:${alert.sensorId}`).emit('water-level:alert', alert);
  }

  emitAnalytics(sensorId: string, analytics: any): void {
    this.io.to(`sensor:${sensorId}`).emit('water-level:analytics', {
      sensorId,
      analytics,
      timestamp: new Date(),
    });
  }

  emitGateRecommendation(gateId: string, recommendation: any): void {
    this.io.to(`gate:${gateId}`).emit('gate:recommendation', recommendation);
    this.io.to('gates:all').emit('gate:recommendation', recommendation);
  }

  emitSystemStatus(status: any): void {
    this.io.emit('system:status', status);
  }

  getConnectedClients(): number {
    return this.io.sockets.sockets.size;
  }

  close(): void {
    this.io.close();
  }
}