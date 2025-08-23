interface ScadaHealthReport {
    status: 'healthy' | 'degraded' | 'critical' | 'failed';
    totalSites: number;
    onlineSites: number;
    offlineSites: number;
    staleDataSites: number;
    lastCheck: string;
}
interface CommandResponse {
    success: boolean;
    commandId?: number;
    message: string;
    error?: any;
}
interface GateCommand {
    gate_name: string;
    gate_level: number;
    fieldId?: string;
    targetFlowRate?: number;
}
export declare class ScadaApiService {
    private readonly baseUrl;
    private readonly authToken?;
    constructor();
    getHealthStatus(): Promise<ScadaHealthReport>;
    getDetailedHealthStatus(): Promise<ScadaHealthReport>;
    sendGateCommand(command: GateCommand): Promise<CommandResponse>;
    getCommandStatus(commandId: number): Promise<any>;
    closeGate(gateName: string, fieldId?: string): Promise<CommandResponse>;
    openGate(gateName: string, level: number, fieldId?: string, targetFlowRate?: number): Promise<CommandResponse>;
    getControlSites(): Promise<any>;
    isScadaAvailable(): Promise<boolean>;
    private getHeaders;
}
export declare const scadaApiService: ScadaApiService;
export {};
//# sourceMappingURL=scada-api.service.d.ts.map