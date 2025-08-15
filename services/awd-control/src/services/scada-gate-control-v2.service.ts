import { logger } from '../utils/logger';
import { getPostgresPool } from '../config/database';
import { publishMessage, KafkaTopics } from '../config/kafka';
import { scadaApiService } from './scada-api.service';

/**
 * SCADA Gate Control Service V2
 * Uses SCADA Integration Service API instead of direct database connection
 */

interface GateCommand {
  gate_name: string;
  gate_level: number; // 1=closed, 2=level1, 3=level2, 4=level3
  startdatetime: Date;
  fieldId: string;
  targetFlowRate?: number; // m³/s
}

export class ScadaGateControlV2Service {
  private awdPool = getPostgresPool();
  
  /**
   * Get available gate control sites
   */
  async getControlSites(): Promise<any[]> {
    try {
      return await scadaApiService.getControlSites();
    } catch (error) {
      logger.error({ error }, 'Failed to get control sites');
      throw error;
    }
  }

  /**
   * Map field ID to station code
   */
  async getStationCodeForField(fieldId: string): Promise<string | null> {
    try {
      // First check if we have a mapping in AWD database
      const result = await this.awdPool.query(`
        SELECT station_code 
        FROM awd.field_gate_mapping 
        WHERE field_id = $1
      `, [fieldId]);

      if (result.rows.length > 0) {
        return result.rows[0].station_code;
      }

      // Fallback to field configuration
      const fieldResult = await this.awdPool.query(`
        SELECT gate_station_code 
        FROM awd.awd_fields 
        WHERE id = $1
      `, [fieldId]);

      return fieldResult.rows[0]?.gate_station_code || null;

    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to get station code for field');
      return null;
    }
  }

  /**
   * Send gate control command via SCADA API
   */
  async sendGateCommand(command: GateCommand): Promise<boolean> {
    try {
      // Send command via SCADA API
      const result = await scadaApiService.sendGateCommand({
        gate_name: command.gate_name,
        gate_level: command.gate_level,
        fieldId: command.fieldId,
        targetFlowRate: command.targetFlowRate
      });

      if (!result.success) {
        logger.error({ result }, 'Gate command failed');
        return false;
      }

      const commandId = result.commandId;

      logger.info({
        commandId,
        gate_name: command.gate_name,
        gate_level: command.gate_level,
        startdatetime: command.startdatetime
      }, 'Gate command sent via SCADA API');

      // Store command reference in AWD database
      await this.awdPool.query(`
        INSERT INTO awd.scada_command_log
        (scada_command_id, field_id, gate_name, gate_level, 
         target_flow_rate, command_time, status)
        VALUES ($1, $2, $3, $4, $5, $6, 'sent')
      `, [
        commandId,
        command.fieldId,
        command.gate_name,
        command.gate_level,
        command.targetFlowRate,
        command.startdatetime
      ]);

      // Publish event
      await publishMessage(KafkaTopics.GATE_CONTROL_COMMANDS, {
        commandId,
        fieldId: command.fieldId,
        gate_name: command.gate_name,
        gate_level: command.gate_level,
        startdatetime: command.startdatetime,
        action: command.gate_level === 1 ? 'close' : 'open'
      });

      return true;

    } catch (error) {
      logger.error({ error, command }, 'Failed to send gate command');
      throw error;
    }
  }

  /**
   * Open gate to achieve target flow rate
   */
  async openGateForFlow(fieldId: string, targetFlowRate: number): Promise<void> {
    try {
      const stationCode = await this.getStationCodeForField(fieldId);
      if (!stationCode) {
        throw new Error(`No station code found for field ${fieldId}`);
      }

      // Call Flow Monitoring Service to calculate required gate level
      const gateLevel = await this.calculateGateLevelForFlow(
        stationCode,
        targetFlowRate
      );

      // Send command to open gate via API
      const result = await scadaApiService.openGate(
        stationCode,
        gateLevel,
        fieldId,
        targetFlowRate
      );

      if (!result.success) {
        throw new Error(result.message);
      }

      logger.info({
        fieldId,
        stationCode,
        targetFlowRate,
        gateLevel,
        commandId: result.commandId
      }, 'Gate opened for target flow');

    } catch (error) {
      logger.error({ error, fieldId, targetFlowRate }, 'Failed to open gate for flow');
      throw error;
    }
  }

  /**
   * Close gate
   */
  async closeGate(fieldId: string): Promise<void> {
    try {
      const stationCode = await this.getStationCodeForField(fieldId);
      if (!stationCode) {
        throw new Error(`No station code found for field ${fieldId}`);
      }

      // Send command to close gate via API
      const result = await scadaApiService.closeGate(stationCode, fieldId);

      if (!result.success) {
        throw new Error(result.message);
      }

      logger.info({
        fieldId,
        stationCode,
        commandId: result.commandId
      }, 'Gate close command sent');

    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to close gate');
      throw error;
    }
  }

  /**
   * Calculate gate level for target flow using hydraulic model
   */
  private async calculateGateLevelForFlow(
    stationCode: string,
    targetFlowRate: number
  ): Promise<number> {
    try {
      // Call Flow Monitoring Service API
      const response = await fetch(
        `${process.env.FLOW_MONITORING_URL}/api/v1/hydraulic/gate-level`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${process.env.SERVICE_AUTH_TOKEN}`
          },
          body: JSON.stringify({
            stationCode,
            targetFlowRate
          })
        }
      );

      if (!response.ok) {
        throw new Error('Failed to calculate gate level');
      }

      const data = await response.json();
      
      // Ensure gate level is between 2-4 (open positions)
      const gateLevel = Math.max(2, Math.min(4, Math.round(data.gateLevel)));
      
      return gateLevel;

    } catch (error) {
      logger.error({ error, stationCode, targetFlowRate }, 'Failed to calculate gate level');
      
      // Fallback calculation based on flow rate
      // Simplified: low flow = level 2, medium = level 3, high = level 4
      if (targetFlowRate < 5) return 2;
      if (targetFlowRate < 10) return 3;
      return 4;
    }
  }

  /**
   * Get gate command status via API
   */
  async getCommandStatus(commandId: number): Promise<{
    complete: boolean;
    gate_level: number;
    startdatetime: Date;
  }> {
    try {
      const status = await scadaApiService.getCommandStatus(commandId);
      
      return {
        complete: status.isComplete,
        gate_level: status.gate_level,
        startdatetime: new Date(status.startdatetime)
      };

    } catch (error) {
      logger.error({ error, commandId }, 'Failed to get command status');
      throw error;
    }
  }

  /**
   * Monitor gate commands for completion
   */
  async monitorGateCommands(): Promise<void> {
    try {
      // Get pending commands from local database
      const result = await this.awdPool.query(`
        SELECT 
          scada_command_id,
          field_id,
          gate_name,
          command_time
        FROM awd.scada_command_log
        WHERE status = 'sent'
          AND command_time > NOW() - INTERVAL '1 hour'
      `);

      for (const command of result.rows) {
        try {
          const status = await this.getCommandStatus(command.scada_command_id);
          
          if (status.complete) {
            // Update status in AWD database
            await this.awdPool.query(`
              UPDATE awd.scada_command_log
              SET 
                status = 'completed',
                completed_at = NOW()
              WHERE scada_command_id = $1
            `, [command.scada_command_id]);

            logger.info({
              commandId: command.scada_command_id,
              fieldId: command.field_id
            }, 'Gate command completed');

            // Publish completion event
            await publishMessage(KafkaTopics.GATE_STATUS_UPDATES, {
              commandId: command.scada_command_id,
              fieldId: command.field_id,
              status: 'completed',
              gate_level: status.gate_level
            });
          }
        } catch (error) {
          logger.error({ error, command }, 'Error checking command status');
        }
      }
    } catch (error) {
      logger.error({ error }, 'Failed to monitor gate commands');
    }
  }

  /**
   * Check SCADA availability
   */
  async checkScadaHealth(): Promise<boolean> {
    try {
      return await scadaApiService.isScadaAvailable();
    } catch (error) {
      logger.error({ error }, 'Failed to check SCADA health');
      return false;
    }
  }

  /**
   * Get canal water levels from Flow Monitoring Service
   */
  async getCanalWaterLevels(canalSection?: string): Promise<any> {
    try {
      const response = await fetch(
        `${process.env.FLOW_MONITORING_URL}/api/v1/water-levels${
          canalSection ? `?section=${canalSection}` : ''
        }`,
        {
          headers: {
            'Authorization': `Bearer ${process.env.SERVICE_AUTH_TOKEN}`
          }
        }
      );

      if (!response.ok) {
        throw new Error('Failed to get canal water levels');
      }

      return await response.json();

    } catch (error) {
      logger.error({ error }, 'Failed to get canal water levels');
      throw error;
    }
  }

  /**
   * Initialize monitoring
   */
  startMonitoring(): void {
    // Monitor command completion every 30 seconds
    setInterval(() => {
      this.monitorGateCommands().catch(error => {
        logger.error({ error }, 'Error in gate command monitoring');
      });
    }, 30000);

    logger.info('SCADA gate monitoring started (using API)');
  }
}

export const scadaGateControlV2Service = new ScadaGateControlV2Service();