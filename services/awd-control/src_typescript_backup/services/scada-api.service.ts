import { logger } from '../utils/logger';

/**
 * SCADA API Service
 * Interfaces with the SCADA Integration Service API
 */

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

export class ScadaApiService {
  private readonly baseUrl: string;
  private readonly authToken?: string;

  constructor() {
    // Use environment variable or default to local/docker service name
    this.baseUrl = process.env.SCADA_SERVICE_URL || 'http://scada-integration:3015';
    this.authToken = process.env.SERVICE_AUTH_TOKEN;
  }

  /**
   * Get SCADA health status
   */
  async getHealthStatus(): Promise<ScadaHealthReport> {
    try {
      const response = await fetch(`${this.baseUrl}/api/v1/scada/health`, {
        headers: this.getHeaders()
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      logger.error({ error }, 'Failed to get SCADA health status');
      throw error;
    }
  }

  /**
   * Get detailed SCADA health status
   */
  async getDetailedHealthStatus(): Promise<ScadaHealthReport> {
    try {
      const response = await fetch(`${this.baseUrl}/api/v1/scada/health/detailed`, {
        headers: this.getHeaders()
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      logger.error({ error }, 'Failed to get detailed SCADA health status');
      throw error;
    }
  }

  /**
   * Send gate control command
   */
  async sendGateCommand(command: GateCommand): Promise<CommandResponse> {
    try {
      const response = await fetch(`${this.baseUrl}/api/v1/scada/command/send`, {
        method: 'POST',
        headers: {
          ...this.getHeaders(),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(command)
      });

      const result = await response.json();

      if (!response.ok) {
        logger.error({ status: response.status, result }, 'Gate command failed');
        return {
          success: false,
          message: result.message || 'Failed to send gate command',
          error: result.error
        };
      }

      return result;
    } catch (error) {
      logger.error({ error, command }, 'Failed to send gate command');
      return {
        success: false,
        message: 'Failed to connect to SCADA service',
        error: error
      };
    }
  }

  /**
   * Get command status
   */
  async getCommandStatus(commandId: number): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/api/v1/scada/command/${commandId}/status`, {
        headers: this.getHeaders()
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      logger.error({ error, commandId }, 'Failed to get command status');
      throw error;
    }
  }

  /**
   * Close gate
   */
  async closeGate(gateName: string, fieldId?: string): Promise<CommandResponse> {
    try {
      const response = await fetch(`${this.baseUrl}/api/v1/scada/gates/${gateName}/close`, {
        method: 'POST',
        headers: {
          ...this.getHeaders(),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ fieldId })
      });

      const result = await response.json();

      if (!response.ok) {
        return {
          success: false,
          message: result.message || 'Failed to close gate',
          error: result.error
        };
      }

      return result;
    } catch (error) {
      logger.error({ error, gateName }, 'Failed to close gate');
      return {
        success: false,
        message: 'Failed to connect to SCADA service',
        error: error
      };
    }
  }

  /**
   * Open gate to specified level
   */
  async openGate(gateName: string, level: number, fieldId?: string, targetFlowRate?: number): Promise<CommandResponse> {
    try {
      const response = await fetch(`${this.baseUrl}/api/v1/scada/gates/${gateName}/open`, {
        method: 'POST',
        headers: {
          ...this.getHeaders(),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ level, fieldId, targetFlowRate })
      });

      const result = await response.json();

      if (!response.ok) {
        return {
          success: false,
          message: result.message || 'Failed to open gate',
          error: result.error
        };
      }

      return result;
    } catch (error) {
      logger.error({ error, gateName, level }, 'Failed to open gate');
      return {
        success: false,
        message: 'Failed to connect to SCADA service',
        error: error
      };
    }
  }

  /**
   * Get control sites
   */
  async getControlSites(): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/api/v1/scada/sites`, {
        headers: this.getHeaders()
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      return data.sites || [];
    } catch (error) {
      logger.error({ error }, 'Failed to get control sites');
      throw error;
    }
  }

  /**
   * Check if SCADA is available
   */
  async isScadaAvailable(): Promise<boolean> {
    try {
      const health = await this.getHealthStatus();
      return health.status === 'healthy' || health.status === 'degraded';
    } catch (error) {
      logger.error({ error }, 'Failed to check SCADA availability');
      return false;
    }
  }

  /**
   * Get request headers
   */
  private getHeaders(): Record<string, string> {
    const headers: Record<string, string> = {};
    
    if (this.authToken) {
      headers['Authorization'] = `Bearer ${this.authToken}`;
    }
    
    return headers;
  }
}

// Export singleton instance
export const scadaApiService = new ScadaApiService();