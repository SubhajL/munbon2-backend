import { scadaPool } from '../config/database';
import { 
  GateCommand, 
  GateCommandStatus, 
  CommandResponse,
  SiteInfo 
} from '../types/scada.types';

export class GateCommandService {
  /**
   * Get available control sites from tb_site
   */
  async getControlSites(): Promise<SiteInfo[]> {
    try {
      const result = await scadaPool.query(`
        SELECT 
          stationcode,
          site_name,
          laststatus,
          dt_laststatus
        FROM tb_site
        WHERE stationcode IS NOT NULL
        ORDER BY site_name
      `);

      return result.rows;
    } catch (error) {
      console.error('Failed to get control sites:', error);
      throw error;
    }
  }

  /**
   * Send gate control command to SCADA
   * Fixed: Removed ID from INSERT statement
   */
  async sendGateCommand(command: GateCommand): Promise<CommandResponse> {
    try {
      // Validate gate level
      if (command.gate_level < 1 || command.gate_level > 4) {
        return {
          success: false,
          message: 'Invalid gate level. Must be between 1 (closed) and 4 (fully open)'
        };
      }

      // Insert command into tb_gatelevel_command (without ID column)
      const result = await scadaPool.query(`
        INSERT INTO tb_gatelevel_command 
        (gate_name, gate_level, startdatetime, completestatus)
        VALUES ($1, $2, $3, $4)
        RETURNING id
      `, [
        command.gate_name,
        command.gate_level,
        command.startdatetime,
        0 // Not complete
      ]);

      const commandId = result.rows[0].id;

      console.log({
        commandId,
        gate_name: command.gate_name,
        gate_level: command.gate_level,
        startdatetime: command.startdatetime
      }, 'Gate command sent to SCADA');

      return {
        success: true,
        commandId,
        message: `Command sent successfully. Gate ${command.gate_name} set to level ${command.gate_level}`
      };

    } catch (error: any) {
      console.error('Failed to send gate command:', error);
      return {
        success: false,
        message: 'Failed to send gate command',
        error: error.message
      };
    }
  }

  /**
   * Get gate command status
   */
  async getCommandStatus(commandId: number): Promise<GateCommandStatus | null> {
    try {
      const result = await scadaPool.query(`
        SELECT 
          id,
          gate_name,
          gate_level,
          startdatetime,
          completestatus
        FROM tb_gatelevel_command
        WHERE id = $1
      `, [commandId]);

      if (result.rows.length === 0) {
        return null;
      }

      return result.rows[0];
    } catch (error) {
      console.error('Failed to get command status:', error);
      throw error;
    }
  }

  /**
   * Get recent gate commands
   */
  async getRecentCommands(limit: number = 50): Promise<GateCommandStatus[]> {
    try {
      const result = await scadaPool.query(`
        SELECT 
          id,
          gate_name,
          gate_level,
          startdatetime,
          completestatus
        FROM tb_gatelevel_command
        ORDER BY startdatetime DESC
        LIMIT $1
      `, [limit]);

      return result.rows;
    } catch (error) {
      console.error('Failed to get recent commands:', error);
      throw error;
    }
  }

  /**
   * Get pending commands (not completed)
   */
  async getPendingCommands(): Promise<GateCommandStatus[]> {
    try {
      const result = await scadaPool.query(`
        SELECT 
          id,
          gate_name,
          gate_level,
          startdatetime,
          completestatus
        FROM tb_gatelevel_command
        WHERE completestatus = 0
          AND startdatetime > NOW() - INTERVAL '1 hour'
        ORDER BY startdatetime DESC
      `);

      return result.rows;
    } catch (error) {
      console.error('Failed to get pending commands:', error);
      throw error;
    }
  }

  /**
   * Monitor command completion
   */
  async monitorCommandCompletion(): Promise<void> {
    try {
      const pendingCommands = await this.getPendingCommands();
      
      for (const command of pendingCommands) {
        const timeSinceStart = Date.now() - new Date(command.startdatetime).getTime();
        const minutesSinceStart = timeSinceStart / (1000 * 60);
        
        if (minutesSinceStart > 5) {
          console.warn({
            commandId: command.id,
            gate_name: command.gate_name,
            minutesSinceStart: Math.round(minutesSinceStart)
          }, 'Gate command taking longer than expected');
        }
      }
      
      console.log(`Monitoring ${pendingCommands.length} pending commands`);
    } catch (error) {
      console.error('Failed to monitor command completion:', error);
    }
  }

  /**
   * Start monitoring loop
   */
  private monitoringTimer: NodeJS.Timer | null = null;

  startMonitoring(): void {
    if (this.monitoringTimer) {
      console.log('Command monitoring already started');
      return;
    }

    console.log('Starting gate command monitoring...');
    
    // Monitor every 30 seconds
    this.monitoringTimer = setInterval(() => {
      this.monitorCommandCompletion().catch(console.error);
    }, 30000);
  }

  stopMonitoring(): void {
    if (this.monitoringTimer) {
      clearInterval(this.monitoringTimer);
      this.monitoringTimer = null;
      console.log('Gate command monitoring stopped');
    }
  }
}

// Export singleton instance
export const gateCommandService = new GateCommandService();