import { CacheService } from './cache.service';
import { TimescaleService } from './timescale.service';
import { WaterLevelReading, WaterLevelAlert } from '../models/water-level.model';
export declare class AlertService {
    private cacheService;
    private timescaleService;
    private alertCooldowns;
    constructor(cacheService: CacheService, timescaleService: TimescaleService);
    checkAlerts(reading: WaterLevelReading): Promise<WaterLevelAlert[]>;
    checkSensorOffline(sensorId: string, lastSeen: Date): Promise<WaterLevelAlert | null>;
    private createAlert;
    private sendNotification;
    private sendToAlertService;
    acknowledgeAlert(alertId: string, acknowledgedBy: string): Promise<void>;
    getActiveAlerts(sensorId?: string): Promise<WaterLevelAlert[]>;
}
//# sourceMappingURL=alert.service.d.ts.map