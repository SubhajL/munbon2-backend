import { WaterLevelReading, WaterLevelAlert } from '../models/water-level.model';
export declare class WebSocketService {
    private io;
    constructor(server: any);
    private setupEventHandlers;
    emitWaterLevelReading(reading: WaterLevelReading): void;
    emitWaterLevelAlert(alert: WaterLevelAlert): void;
    emitAnalytics(sensorId: string, analytics: any): void;
    emitGateRecommendation(gateId: string, recommendation: any): void;
    emitSystemStatus(status: any): void;
    getConnectedClients(): number;
    close(): void;
}
//# sourceMappingURL=websocket.service.d.ts.map