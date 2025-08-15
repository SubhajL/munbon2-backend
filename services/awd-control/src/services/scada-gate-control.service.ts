import { Pool } from 'pg';
import { logger } from '../utils/logger';
import { getPostgresPool } from '../config/database';
import { publishMessage, KafkaTopics } from '../config/kafka';

/**
 * SCADA Gate Control Service
 * Interfaces with the actual SCADA database (db_scada) to control irrigation gates
 */

interface GateCommand {
  gate_name: string;
  gate_level: number; // 1=closed, 2=level1, 3=level2, 4=level3
  startdatetime: Date;
  fieldId: string;
  targetFlowRate?: number; // m³/s
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

export class ScadaGateControlService {
  private scadaPool: Pool;
  private awdPool: Pool;
  
  constructor() {
    // Initialize SCADA database connection (same as AOS data)
    this.scadaPool = new Pool({
      host: process.env.SCADA_DB_HOST || '43.209.22.250',
      port: parseInt(process.env.SCADA_DB_PORT || '5432'),
      database: process.env.SCADA_DB_NAME || 'db_scada',
      user: process.env.SCADA_DB_USER || 'postgres',
      password: process.env.SCADA_DB_PASSWORD || 'P@ssw0rd123!',
      max: 10,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 2000,
    });

    // AWD database pool for local data
    this.awdPool = getPostgresPool();
  }

  /**
   * Get available gate control sites from tb_site
   */
  async getControlSites(): Promise<SiteInfo[]> {
    try {
      const result = await this.scadaPool.query(`
        SELECT 
          stationcode,
          site_name,
          4 as max_gate_levels -- Most sites have 4 levels
        FROM tb_site
        WHERE stationcode IS NOT NULL
        LIMIT 20
      `);

      return result.rows;
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
   * Send gate control command to SCADA
   */
  async sendGateCommand(command: GateCommand): Promise<boolean> {
    try {
      // Insert command into tb_gatelevel_command (Fixed: removed ID column)
      const result = await this.scadaPool.query(`
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

      logger.info({
        commandId,
        gate_name: command.gate_name,
        gate_level: command.gate_level,
        startdatetime: command.startdatetime
      }, 'Gate command sent to SCADA');

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

      // Send command to open gate
      await this.sendGateCommand({
        gate_name: stationCode,
        gate_level: gateLevel,
        startdatetime: new Date(),
        fieldId,
        targetFlowRate
      });

      logger.info({
        fieldId,
        stationCode,
        targetFlowRate,
        gateLevel
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

      // Send command to close gate (level = 1)
      await this.sendGateCommand({
        gate_name: stationCode,
        gate_level: 1,
        startdatetime: new Date(),
        fieldId
      });

      logger.info({
        fieldId,
        stationCode
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
   * Get gate command status
   */
  async getCommandStatus(commandId: number): Promise<{
    complete: boolean;
    gate_level: number;
    startdatetime: Date;
  }> {
    try {
      const result = await this.scadaPool.query(`
        SELECT 
          gate_level,
          startdatetime,
          completestatus
        FROM tb_gatelevel_command
        WHERE id = $1
      `, [commandId]);

      if (result.rows.length === 0) {
        throw new Error('Command not found');
      }

      const row = result.rows[0];
      return {
        complete: row.completestatus === 1,
        gate_level: row.gate_level,
        startdatetime: row.startdatetime
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
      // Get pending commands
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

    logger.info('SCADA gate monitoring started');
  }

  /**
   * Cleanup connections
   */
  async disconnect(): Promise<void> {
    await this.scadaPool.end();
  }
}

export const scadaGateControlService = new ScadaGateControlService();