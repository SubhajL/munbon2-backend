export interface SiteInfo {
  stationcode: string;
  site_name: string;
  laststatus: 'ONLINE' | 'OFFLINE' | null;
  dt_laststatus: Date | null;
  location?: {
    lat: number;
    lon: number;
  };
}

export interface GateCommand {
  gate_name: string;
  gate_level: number; // 1=closed, 2=level1, 3=level2, 4=level3
  startdatetime: Date;
  fieldId?: string;
  targetFlowRate?: number; // m³/s
}

export interface GateCommandStatus {
  id: number;
  gate_name: string;
  gate_level: number;
  startdatetime: Date;
  completestatus: number; // 0=pending, 1=complete
}

export enum HealthStatus {
  HEALTHY = 'healthy',
  DEGRADED = 'degraded',
  CRITICAL = 'critical',
  FAILED = 'failed'
}

export interface SiteHealthStatus {
  stationcode: string;
  site_name: string;
  status: 'ONLINE' | 'OFFLINE' | null;
  lastUpdateTime: Date | null;
  minutesSinceUpdate: number | null;
  health: HealthStatus;
}

export interface ScadaHealthReport {
  status: HealthStatus;
  totalSites: number;
  onlineSites: number;
  offlineSites: number;
  staleDataSites: number;
  lastCheck: Date;
  details?: SiteHealthStatus[];
}

export interface CommandResponse {
  success: boolean;
  commandId?: number;
  message: string;
  error?: any;
}