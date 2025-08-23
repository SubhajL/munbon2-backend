import { CacheService } from '../services/cache.service';
import { AlertService } from '../services/alert.service';
import { MqttService } from '../services/mqtt.service';
import { WebSocketService } from '../services/websocket.service';
export declare class DataProcessor {
    private cacheService;
    private alertService;
    private mqttService;
    private websocketService;
    constructor(cacheService: CacheService, alertService: AlertService, mqttService: MqttService, websocketService: WebSocketService);
    start(): Promise<void>;
    private processMoistureData;
    private transformToMoistureReading;
}
//# sourceMappingURL=data-processor.d.ts.map