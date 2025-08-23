interface GateCommand {
    gate_name: string;
    gate_level: number;
    startdatetime: Date;
    fieldId: string;
    targetFlowRate?: number;
}
interface SiteInfo {
    stationcode: string;
    site_name: string;
    max_gate_levels: number;
    location?: {
        lat: number;
        lon: number;
    };
}
export declare class ScadaGateControlService {
    private scadaPool;
    private awdPool;
    constructor();
    getControlSites(): Promise<SiteInfo[]>;
    getStationCodeForField(fieldId: string): Promise<string | null>;
    sendGateCommand(command: GateCommand): Promise<boolean>;
    openGateForFlow(fieldId: string, targetFlowRate: number): Promise<void>;
    closeGate(fieldId: string): Promise<void>;
    private calculateGateLevelForFlow;
    getCommandStatus(commandId: number): Promise<{
        complete: boolean;
        gate_level: number;
        startdatetime: Date;
    }>;
    monitorGateCommands(): Promise<void>;
    getCanalWaterLevels(canalSection?: string): Promise<any>;
    startMonitoring(): void;
    disconnect(): Promise<void>;
}
export declare const scadaGateControlService: ScadaGateControlService;
export {};
//# sourceMappingURL=scada-gate-control.service.d.ts.map