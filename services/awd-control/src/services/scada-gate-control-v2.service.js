"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.scadaGateControlV2Service = exports.ScadaGateControlV2Service = void 0;
const logger_1 = require("../utils/logger");
const database_1 = require("../config/database");
const kafka_1 = require("../config/kafka");
const scada_api_service_1 = require("./scada-api.service");
class ScadaGateControlV2Service {
    awdPool = (0, database_1.getPostgresPool)();
    async getControlSites() {
        try {
            return await scada_api_service_1.scadaApiService.getControlSites();
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to get control sites');
            throw error;
        }
    }
    async getStationCodeForField(fieldId) {
        try {
            const result = await this.awdPool.query(`
        SELECT station_code 
        FROM awd.field_gate_mapping 
        WHERE field_id = $1
      `, [fieldId]);
            if (result.rows.length > 0) {
                return result.rows[0].station_code;
            }
            const fieldResult = await this.awdPool.query(`
        SELECT gate_station_code 
        FROM awd.awd_fields 
        WHERE id = $1
      `, [fieldId]);
            return fieldResult.rows[0]?.gate_station_code || null;
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId }, 'Failed to get station code for field');
            return null;
        }
    }
    async sendGateCommand(command) {
        try {
            const result = await scada_api_service_1.scadaApiService.sendGateCommand({
                gate_name: command.gate_name,
                gate_level: command.gate_level,
                fieldId: command.fieldId,
                targetFlowRate: command.targetFlowRate
            });
            if (!result.success) {
                logger_1.logger.error({ result }, 'Gate command failed');
                return false;
            }
            const commandId = result.commandId;
            logger_1.logger.info({
                commandId,
                gate_name: command.gate_name,
                gate_level: command.gate_level,
                startdatetime: command.startdatetime
            }, 'Gate command sent via SCADA API');
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
            await (0, kafka_1.publishMessage)(kafka_1.KafkaTopics.GATE_CONTROL_COMMANDS, {
                commandId,
                fieldId: command.fieldId,
                gate_name: command.gate_name,
                gate_level: command.gate_level,
                startdatetime: command.startdatetime,
                action: command.gate_level === 1 ? 'close' : 'open'
            });
            return true;
        }
        catch (error) {
            logger_1.logger.error({ error, command }, 'Failed to send gate command');
            throw error;
        }
    }
    async openGateForFlow(fieldId, targetFlowRate) {
        try {
            const stationCode = await this.getStationCodeForField(fieldId);
            if (!stationCode) {
                throw new Error(`No station code found for field ${fieldId}`);
            }
            const gateLevel = await this.calculateGateLevelForFlow(stationCode, targetFlowRate);
            const result = await scada_api_service_1.scadaApiService.openGate(stationCode, gateLevel, fieldId, targetFlowRate);
            if (!result.success) {
                throw new Error(result.message);
            }
            logger_1.logger.info({
                fieldId,
                stationCode,
                targetFlowRate,
                gateLevel,
                commandId: result.commandId
            }, 'Gate opened for target flow');
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId, targetFlowRate }, 'Failed to open gate for flow');
            throw error;
        }
    }
    async closeGate(fieldId) {
        try {
            const stationCode = await this.getStationCodeForField(fieldId);
            if (!stationCode) {
                throw new Error(`No station code found for field ${fieldId}`);
            }
            const result = await scada_api_service_1.scadaApiService.closeGate(stationCode, fieldId);
            if (!result.success) {
                throw new Error(result.message);
            }
            logger_1.logger.info({
                fieldId,
                stationCode,
                commandId: result.commandId
            }, 'Gate close command sent');
        }
        catch (error) {
            logger_1.logger.error({ error, fieldId }, 'Failed to close gate');
            throw error;
        }
    }
    async calculateGateLevelForFlow(stationCode, targetFlowRate) {
        try {
            const response = await fetch(`${process.env.FLOW_MONITORING_URL}/api/v1/hydraulic/gate-level`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${process.env.SERVICE_AUTH_TOKEN}`
                },
                body: JSON.stringify({
                    stationCode,
                    targetFlowRate
                })
            });
            if (!response.ok) {
                throw new Error('Failed to calculate gate level');
            }
            const data = await response.json();
            const gateLevel = Math.max(2, Math.min(4, Math.round(data.gateLevel)));
            return gateLevel;
        }
        catch (error) {
            logger_1.logger.error({ error, stationCode, targetFlowRate }, 'Failed to calculate gate level');
            if (targetFlowRate < 5)
                return 2;
            if (targetFlowRate < 10)
                return 3;
            return 4;
        }
    }
    async getCommandStatus(commandId) {
        try {
            const status = await scada_api_service_1.scadaApiService.getCommandStatus(commandId);
            return {
                complete: status.isComplete,
                gate_level: status.gate_level,
                startdatetime: new Date(status.startdatetime)
            };
        }
        catch (error) {
            logger_1.logger.error({ error, commandId }, 'Failed to get command status');
            throw error;
        }
    }
    async monitorGateCommands() {
        try {
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
                        await this.awdPool.query(`
              UPDATE awd.scada_command_log
              SET 
                status = 'completed',
                completed_at = NOW()
              WHERE scada_command_id = $1
            `, [command.scada_command_id]);
                        logger_1.logger.info({
                            commandId: command.scada_command_id,
                            fieldId: command.field_id
                        }, 'Gate command completed');
                        await (0, kafka_1.publishMessage)(kafka_1.KafkaTopics.GATE_STATUS_UPDATES, {
                            commandId: command.scada_command_id,
                            fieldId: command.field_id,
                            status: 'completed',
                            gate_level: status.gate_level
                        });
                    }
                }
                catch (error) {
                    logger_1.logger.error({ error, command }, 'Error checking command status');
                }
            }
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to monitor gate commands');
        }
    }
    async checkScadaHealth() {
        try {
            return await scada_api_service_1.scadaApiService.isScadaAvailable();
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to check SCADA health');
            return false;
        }
    }
    async getCanalWaterLevels(canalSection) {
        try {
            const response = await fetch(`${process.env.FLOW_MONITORING_URL}/api/v1/water-levels${canalSection ? `?section=${canalSection}` : ''}`, {
                headers: {
                    'Authorization': `Bearer ${process.env.SERVICE_AUTH_TOKEN}`
                }
            });
            if (!response.ok) {
                throw new Error('Failed to get canal water levels');
            }
            return await response.json();
        }
        catch (error) {
            logger_1.logger.error({ error }, 'Failed to get canal water levels');
            throw error;
        }
    }
    startMonitoring() {
        setInterval(() => {
            this.monitorGateCommands().catch(error => {
                logger_1.logger.error({ error }, 'Error in gate command monitoring');
            });
        }, 30000);
        logger_1.logger.info('SCADA gate monitoring started (using API)');
    }
}
exports.ScadaGateControlV2Service = ScadaGateControlV2Service;
exports.scadaGateControlV2Service = new ScadaGateControlV2Service();
//# sourceMappingURL=scada-gate-control-v2.service.js.map