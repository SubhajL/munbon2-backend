import { CacheService } from './cache.service';
import { MoistureReading, MoistureAlert } from '../models/moisture.model';
export declare class AlertService {
    private cacheService;
    private alertCooldowns;
    constructor(cacheService: CacheService);
    checkAlerts(reading: MoistureReading): Promise<MoistureAlert[]>;
    checkSensorOffline(sensorId: string, lastSeen: Date): Promise<MoistureAlert | null>;
    private createAlert;
    private sendNotification;
    private sendToAlertService;
    acknowledgeAlert(alertId: string, acknowledgedBy: string): Promise<void>;
    getActiveAlerts(sensorId?: string): Promise<MoistureAlert[]>;
}
//# sourceMappingURL=alert.service.d.ts.map