interface GateCommand {
    gate_name: string;
    gate_level: number;
    startdatetime: Date;
    fieldId: string;
    targetFlowRate?: number;
}
export declare class ScadaGateControlV2Service {
    private awdPool;
    getControlSites(): Promise<any[]>;
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
    checkScadaHealth(): Promise<boolean>;
    getCanalWaterLevels(canalSection?: string): Promise<any>;
    startMonitoring(): void;
}
export declare const scadaGateControlV2Service: ScadaGateControlV2Service;
export {};
//# sourceMappingURL=scada-gate-control-v2.service.d.ts.map