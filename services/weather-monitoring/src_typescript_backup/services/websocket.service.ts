import { Server as HttpServer } from 'http';
import { Server as SocketIOServer, Socket } from 'socket.io';
import { config } from '../config';
import { logger } from '../utils/logger';
import jwt from 'jsonwebtoken';
import { WeatherReading, WeatherAlert, WeatherForecast } from '../models/weather.model';

export class WebSocketService {
  private io: SocketIOServer;
  private connections: Map<string, Socket> = new Map();
  private subscriptions: Map<string, Set<string>> = new Map();

  constructor(server: HttpServer) {
    this.io = new SocketIOServer(server, {
      cors: {
        origin: config.cors.origin.split(','),
        credentials: true,
      },
      pingTimeout: 60000,
      pingInterval: 25000,
    });

    this.setupMiddleware();
    this.setupEventHandlers();
  }

  private setupMiddleware(): void {
    // Authentication middleware
    this.io.use(async (socket, next) => {
      try {
        const token = socket.handshake.auth.token || socket.handshake.headers.authorization?.split(' ')[1];
        
        if (!token) {
          return next(new Error('Authentication required'));
        }

        // Verify JWT token
        const decoded = jwt.verify(token, config.jwtSecret) as any;
        socket.data.userId = decoded.userId;
        socket.data.role = decoded.role;
        
        next();
      } catch (error) {
        logger.error({ error }, 'WebSocket authentication failed');
        next(new Error('Invalid token'));
      }
    });
  }

  private setupEventHandlers(): void {
    this.io.on('connection', (socket) => {
      const userId = socket.data.userId;
      logger.info({ userId, socketId: socket.id }, 'Client connected');
      
      this.connections.set(socket.id, socket);

      // Handle subscription requests
      socket.on('subscribe:weather', (data) => this.handleWeatherSubscription(socket, data));
      socket.on('subscribe:alerts', (data) => this.handleAlertSubscription(socket, data));
      socket.on('subscribe:forecast', (data) => this.handleForecastSubscription(socket, data));
      socket.on('subscribe:analytics', (data) => this.handleAnalyticsSubscription(socket, data));
      socket.on('subscribe:irrigation', (data) => this.handleIrrigationSubscription(socket, data));

      // Handle unsubscription requests
      socket.on('unsubscribe:weather', (data) => this.handleUnsubscribe(socket, 'weather', data));
      socket.on('unsubscribe:alerts', (data) => this.handleUnsubscribe(socket, 'alerts', data));
      socket.on('unsubscribe:forecast', (data) => this.handleUnsubscribe(socket, 'forecast', data));
      socket.on('unsubscribe:analytics', (data) => this.handleUnsubscribe(socket, 'analytics', data));
      socket.on('unsubscribe:irrigation', (data) => this.handleUnsubscribe(socket, 'irrigation', data));

      // Handle real-time queries
      socket.on('query:current', (data, callback) => this.handleCurrentQuery(socket, data, callback));
      socket.on('query:stations', (data, callback) => this.handleStationsQuery(socket, data, callback));

      // Handle disconnection
      socket.on('disconnect', () => {
        logger.info({ userId, socketId: socket.id }, 'Client disconnected');
        this.handleDisconnect(socket);
      });

      // Send initial connection confirmation
      socket.emit('connected', {
        message: 'Connected to Weather Monitoring Service',
        timestamp: new Date(),
        features: [
          'weather-updates',
          'alerts',
          'forecasts',
          'analytics',
          'irrigation-recommendations',
        ],
      });
    });
  }

  private handleWeatherSubscription(socket: Socket, data: any): void {
    const { location, stationIds, radius } = data;
    const subscriptionKey = this.createSubscriptionKey('weather', location, stationIds);
    
    // Add to subscription tracking
    if (!this.subscriptions.has(subscriptionKey)) {
      this.subscriptions.set(subscriptionKey, new Set());
    }
    this.subscriptions.get(subscriptionKey)!.add(socket.id);
    
    // Join appropriate room
    socket.join(subscriptionKey);
    
    logger.debug({ 
      socketId: socket.id, 
      subscriptionKey,
      location,
      stationIds 
    }, 'Weather subscription added');
    
    socket.emit('subscribed:weather', {
      subscriptionKey,
      location,
      stationIds,
      radius,
    });
  }

  private handleAlertSubscription(socket: Socket, data: any): void {
    const { location, radius, severity, types } = data;
    const subscriptionKey = 'alerts:all'; // For now, subscribe to all alerts
    
    socket.join(subscriptionKey);
    
    socket.emit('subscribed:alerts', {
      subscriptionKey,
      location,
      radius,
      severity,
      types,
    });
  }

  private handleForecastSubscription(socket: Socket, data: any): void {
    const { location, days } = data;
    const subscriptionKey = this.createSubscriptionKey('forecast', location);
    
    socket.join(subscriptionKey);
    
    socket.emit('subscribed:forecast', {
      subscriptionKey,
      location,
      days,
    });
  }

  private handleAnalyticsSubscription(socket: Socket, data: any): void {
    const { location, period } = data;
    const subscriptionKey = this.createSubscriptionKey('analytics', location);
    
    socket.join(subscriptionKey);
    
    socket.emit('subscribed:analytics', {
      subscriptionKey,
      location,
      period,
    });
  }

  private handleIrrigationSubscription(socket: Socket, data: any): void {
    const { location, cropType } = data;
    const subscriptionKey = this.createSubscriptionKey('irrigation', location);
    
    socket.join(subscriptionKey);
    
    socket.emit('subscribed:irrigation', {
      subscriptionKey,
      location,
      cropType,
    });
  }

  private handleUnsubscribe(socket: Socket, type: string, data: any): void {
    const subscriptionKey = this.createSubscriptionKey(type, data.location, data.stationIds);
    
    socket.leave(subscriptionKey);
    
    // Remove from subscription tracking
    const subscribers = this.subscriptions.get(subscriptionKey);
    if (subscribers) {
      subscribers.delete(socket.id);
      if (subscribers.size === 0) {
        this.subscriptions.delete(subscriptionKey);
      }
    }
    
    socket.emit(`unsubscribed:${type}`, { subscriptionKey });
  }

  private handleCurrentQuery(socket: Socket, data: any, callback: Function): void {
    // This would typically query the database
    // For now, send a mock response
    callback({
      success: true,
      data: {
        message: 'Current weather query would be processed here',
        location: data.location,
        timestamp: new Date(),
      },
    });
  }

  private handleStationsQuery(socket: Socket, data: any, callback: Function): void {
    // This would typically query the database
    // For now, send a mock response
    callback({
      success: true,
      data: {
        message: 'Stations query would be processed here',
        location: data.location,
        radius: data.radius,
        timestamp: new Date(),
      },
    });
  }

  private handleDisconnect(socket: Socket): void {
    // Remove from all subscriptions
    this.subscriptions.forEach((subscribers, key) => {
      subscribers.delete(socket.id);
      if (subscribers.size === 0) {
        this.subscriptions.delete(key);
      }
    });
    
    // Remove from connections
    this.connections.delete(socket.id);
  }

  private createSubscriptionKey(type: string, location?: { lat: number; lng: number }, stationIds?: string[]): string {
    if (stationIds && stationIds.length > 0) {
      return `${type}:stations:${stationIds.sort().join(',')}`;
    }
    if (location) {
      // Round to 2 decimal places for grouping nearby locations
      const lat = Math.round(location.lat * 100) / 100;
      const lng = Math.round(location.lng * 100) / 100;
      return `${type}:location:${lat},${lng}`;
    }
    return `${type}:all`;
  }

  // Broadcast methods
  broadcastWeatherUpdate(reading: WeatherReading): void {
    const locationKey = this.createSubscriptionKey('weather', reading.location);
    const stationKey = this.createSubscriptionKey('weather', undefined, [reading.stationId]);
    const allKey = 'weather:all';
    
    const event = 'weather:update';
    const data = {
      ...reading,
      timestamp: reading.timestamp.toISOString(),
    };
    
    // Emit to specific rooms
    this.io.to(locationKey).emit(event, data);
    this.io.to(stationKey).emit(event, data);
    this.io.to(allKey).emit(event, data);
    
    logger.debug({ 
      event,
      stationId: reading.stationId,
      rooms: [locationKey, stationKey, allKey]
    }, 'Broadcasted weather update');
  }

  broadcastAlert(alert: WeatherAlert): void {
    const event = 'alert:new';
    const data = {
      ...alert,
      timestamp: alert.timestamp.toISOString(),
      validFrom: alert.validFrom.toISOString(),
      validUntil: alert.validUntil.toISOString(),
    };
    
    // Broadcast to all alert subscribers
    this.io.to('alerts:all').emit(event, data);
    
    // Also broadcast to location-specific rooms if applicable
    if (alert.affectedArea.type === 'point') {
      const [lng, lat] = alert.affectedArea.coordinates;
      const locationKey = this.createSubscriptionKey('alerts', { lat, lng });
      this.io.to(locationKey).emit(event, data);
    }
    
    logger.info({ 
      event,
      alertId: alert.id,
      type: alert.type,
      severity: alert.severity 
    }, 'Broadcasted alert');
  }

  broadcastForecast(location: { lat: number; lng: number }, forecast: WeatherForecast[]): void {
    const locationKey = this.createSubscriptionKey('forecast', location);
    const event = 'forecast:update';
    
    this.io.to(locationKey).emit(event, {
      location,
      forecast,
      timestamp: new Date().toISOString(),
    });
  }

  broadcastAnalytics(location: { lat: number; lng: number }, analytics: any): void {
    const locationKey = this.createSubscriptionKey('analytics', location);
    const event = 'analytics:update';
    
    this.io.to(locationKey).emit(event, {
      location,
      analytics,
      timestamp: new Date().toISOString(),
    });
  }

  broadcastIrrigationRecommendation(recommendation: any): void {
    const locationKey = this.createSubscriptionKey('irrigation', recommendation.location);
    const event = 'irrigation:recommendation';
    
    this.io.to(locationKey).emit(event, {
      ...recommendation,
      timestamp: new Date().toISOString(),
    });
  }

  // Utility methods
  getConnectionCount(): number {
    return this.connections.size;
  }

  getSubscriptionCount(): number {
    return this.subscriptions.size;
  }

  getDetailedStats(): any {
    const stats = {
      connections: this.connections.size,
      subscriptions: {},
      rooms: {},
    };
    
    // Count subscriptions by type
    this.subscriptions.forEach((subscribers, key) => {
      const type = key.split(':')[0];
      stats.subscriptions[type] = (stats.subscriptions[type] || 0) + subscribers.size;
    });
    
    // Get room sizes
    const rooms = this.io.sockets.adapter.rooms;
    rooms.forEach((sockets, room) => {
      if (!room.startsWith('socket:')) { // Exclude individual socket rooms
        stats.rooms[room] = sockets.size;
      }
    });
    
    return stats;
  }
}