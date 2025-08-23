import { CacheService } from '../services/cache.service';
import { DatabaseService } from '../services/database.service';
import { AlertService } from '../services/alert.service';
import { MqttService } from '../services/mqtt.service';
import { WebSocketService } from '../services/websocket.service';
export declare class DataProcessor {
    private cacheService;
    private databaseService;
    private alertService;
    private mqttService;
    private websocketService;
    private processInterval;
    constructor(cacheService: CacheService, databaseService: DatabaseService, alertService: AlertService, mqttService: MqttService, websocketService: WebSocketService);
    start(): void;
    stop(): void;
    private subscribeToDataUpdates;
    private processQueuedData;
    private processWeatherData;
    private validateDataQuality;
    private broadcastUpdates;
    private logMetrics;
}
//# sourceMappingURL=data-processor.d.ts.map