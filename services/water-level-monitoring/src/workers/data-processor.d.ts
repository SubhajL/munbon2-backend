import { CacheService } from '../services/cache.service';
import { AlertService } from '../services/alert.service';
import { MqttService } from '../services/mqtt.service';
import { WebSocketService } from '../services/websocket.service';
import { GateControlService } from '../services/gate-control.service';
export declare class DataProcessor {
    private cacheService;
    private alertService;
    private mqttService;
    private websocketService;
    private gateControlService;
    constructor(cacheService: CacheService, alertService: AlertService, mqttService: MqttService, websocketService: WebSocketService, gateControlService: GateControlService);
    start(): Promise<void>;
    private processWaterLevelData;
    private transformToWaterLevelReading;
    private processGateCommand;
}
//# sourceMappingURL=data-processor.d.ts.map