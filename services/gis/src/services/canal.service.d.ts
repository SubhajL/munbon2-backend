import { Canal } from '../models/canal.entity';
import { Gate } from '../models/gate.entity';
import { LineString } from 'geojson';
interface CanalQuery {
    page: number;
    limit: number;
    includeGeometry?: boolean;
    filters?: {
        type?: string;
        status?: string;
        level?: number;
    };
}
interface FlowHistory {
    timestamp: Date;
    flowRate: number;
    sensorId?: string;
}
interface NetworkNode {
    id: string;
    type: 'canal' | 'gate' | 'pump' | 'junction';
    name: string;
    connections: string[];
    properties: any;
}
declare class CanalService {
    private canalRepository;
    private gateRepository;
    constructor();
    getAllCanals(query: CanalQuery): Promise<any>;
    getCanalById(id: string): Promise<Canal | null>;
    queryCanals(query: any): Promise<Canal[]>;
    getFlowHistory(canalId: string, options: any): Promise<FlowHistory[]>;
    getConnectedGates(canalId: string): Promise<Gate[]>;
    getNetworkTopology(options: any): Promise<NetworkNode[]>;
    updateCanalStatus(id: string, statusData: any): Promise<Canal>;
    updateFlowRate(id: string, flowData: any): Promise<any>;
    getMaintenanceHistory(id: string, options: any): Promise<any>;
    createCanal(data: any): Promise<Canal>;
    updateCanal(id: string, data: any): Promise<Canal>;
    updateCanalGeometry(id: string, geometry: LineString): Promise<Canal>;
    deleteCanal(id: string): Promise<void>;
    analyzeNetwork(analysisData: any): Promise<any>;
    private analyzeConnectivity;
    private analyzeFlowPath;
    private analyzeCapacity;
    optimizeFlow(optimizationData: any): Promise<any>;
    identifyBottlenecks(options: any): Promise<any[]>;
    private getBottleneckRecommendations;
    bulkImportCanals(data: any, format: string): Promise<any>;
    bulkUpdateCanals(canals: any[]): Promise<any>;
}
export declare const canalService: CanalService;
export {};
//# sourceMappingURL=canal.service.d.ts.map