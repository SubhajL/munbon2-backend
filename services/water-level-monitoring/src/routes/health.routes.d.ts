import { Router } from 'express';
import { TimescaleService } from '../services/timescale.service';
import { CacheService } from '../services/cache.service';
import { MqttService } from '../services/mqtt.service';
import { WebSocketService } from '../services/websocket.service';
export declare function createHealthRoutes(timescaleService: TimescaleService, cacheService: CacheService, mqttService: MqttService, websocketService: WebSocketService): Router;
//# sourceMappingURL=health.routes.d.ts.map