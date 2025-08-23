export interface TunnelConfig {
    publicUrl: string;
    healthCheckUrl: string;
    localPort: number;
    endpoints: {
        telemetry: string;
        current: string;
        history: string;
        alerts: string;
        profile: string;
        irrigation: string;
    };
}
export declare const tunnelConfig: TunnelConfig;
export declare function getTunnelUrl(endpoint: keyof typeof tunnelConfig.endpoints): string;
export declare function displayTunnelInfo(): void;
//# sourceMappingURL=tunnel.config.d.ts.map