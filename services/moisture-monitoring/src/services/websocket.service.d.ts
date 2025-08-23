import { MoistureReading, MoistureAlert } from '../models/moisture.model';
export declare class WebSocketService {
    private io;
    constructor(server: any);
    private setupEventHandlers;
    emitMoistureReading(reading: MoistureReading): void;
    emitMoistureAlert(alert: MoistureAlert): void;
    emitAnalytics(sensorId: string, analytics: any): void;
    emitSystemStatus(status: any): void;
    getConnectedClients(): number;
    close(): void;
}
//# sourceMappingURL=websocket.service.d.ts.map