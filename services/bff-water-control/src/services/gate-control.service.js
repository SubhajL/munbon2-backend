const { writeGateCommand, checkCommandStatus } = require('../config/database');
const gateLevels = require('../config/gate-levels.json');
const winston = require('winston');
const { v4: uuidv4 } = require('uuid');

const logger = winston.createLogger({
  level: 'info',
  format: winston.format.json(),
  transports: [
    new winston.transports.Console({
      format: winston.format.simple()
    })
  ]
});

class GateControlService {
  constructor() {
    this.automaticGates = gateLevels.automatic_gates;
    this.commandHistory = new Map();
  }

  /**
   * Get cumulative gate level in cm for a specific gate and level
   * @param {string} gateName - Gate alias name
   * @param {number} level - Target level (1-4)
   * @returns {number} - Cumulative gate opening in cm
   */
  getGateLevelCm(gateName, level) {
    const gateConfig = this.automaticGates[gateName];
    if (!gateConfig) {
      throw new Error(`Gate ${gateName} not found in configuration`);
    }

    const levelKey = `level_${level}`;
    const cumulativeLevel = gateConfig.cumulative_levels[levelKey];
    
    if (cumulativeLevel === undefined) {
      throw new Error(`Level ${level} not defined for gate ${gateName}`);
    }

    return cumulativeLevel;
  }

  /**
   * Control automatic gate through SCADA
   * @param {Object} params - Control parameters
   * @param {string} params.gateName - Gate alias name
   * @param {number} params.targetLevel - Target level (1-4)
   * @param {Date} params.startDateTime - When to execute
   * @param {string} params.reason - Reason for control
   * @returns {Promise<Object>} - Command result
   */
  async controlAutomaticGate(params) {
    const { gateName, targetLevel, startDateTime, reason } = params;
    
    try {
      // Validate gate exists
      if (!this.automaticGates[gateName]) {
        throw new Error(`Gate ${gateName} is not an automatic gate`);
      }

      // Get cumulative level
      const gateLevel = this.getGateLevelCm(gateName, targetLevel);
      
      // Create command
      const command = {
        gateName,
        gateLevel,
        startDateTime: startDateTime || new Date(),
        reason
      };

      // Write to SCADA database
      const result = await writeGateCommand(command);
      
      // Store in history
      const commandId = uuidv4();
      this.commandHistory.set(commandId, {
        ...result,
        type: 'automatic',
        targetLevel,
        createdAt: new Date()
      });

      logger.info(`Automatic gate command sent: ${gateName} to Level ${targetLevel} (${gateLevel}cm)`);

      return {
        commandId,
        scadaCommandId: result.commandId,
        gateName,
        targetLevel,
        gateLevel,
        startDateTime: command.startDateTime,
        status: 'pending'
      };
    } catch (error) {
      logger.error('Failed to control automatic gate:', error);
      throw error;
    }
  }

  /**
   * Send multiple gate commands for closing sequence
   * @param {Object} params - Control parameters
   * @param {string} params.gateName - Gate alias name
   * @param {number} params.fromLevel - Starting level
   * @param {number} params.toLevel - Target level
   * @param {Date} params.startDateTime - When to start sequence
   * @param {number} params.intervalMinutes - Minutes between commands
   * @returns {Promise<Array>} - Array of command results
   */
  async controlGateSequence(params) {
    const { gateName, fromLevel, toLevel, startDateTime, intervalMinutes = 5 } = params;
    
    const commands = [];
    const startTime = new Date(startDateTime || new Date());
    
    // Determine direction
    const step = fromLevel > toLevel ? -1 : 1;
    
    let commandTime = new Date(startTime);
    for (let level = fromLevel; level !== toLevel + step; level += step) {
      const command = await this.controlAutomaticGate({
        gateName,
        targetLevel: level,
        startDateTime: new Date(commandTime),
        reason: `Sequence: Level ${fromLevel} to ${toLevel}`
      });
      
      commands.push(command);
      
      // Add interval for next command
      commandTime.setMinutes(commandTime.getMinutes() + intervalMinutes);
    }
    
    return commands;
  }

  /**
   * Generate job order for manual gates
   * @param {Object} params - Job order parameters
   * @param {Array} params.gates - Array of manual gate configurations
   * @param {string} params.operatorName - Assigned operator
   * @param {Date} params.executionDate - When to execute
   * @returns {Object} - Job order details
   */
  generateManualGateJobOrder(params) {
    const { gates, operatorName, executionDate } = params;
    
    const jobOrderId = uuidv4();
    const jobOrder = {
      id: jobOrderId,
      type: 'manual_gate_operation',
      operatorName,
      executionDate: executionDate || new Date(),
      gates: gates.map(gate => ({
        gateName: gate.gateName,
        location: gate.location,
        zone: gate.zone,
        currentHeight: gate.currentHeight || 0,
        targetHeight: gate.targetHeight,
        openTime: gate.openTime,
        closeTime: gate.closeTime,
        instructions: this.generateGateInstructions(gate)
      })),
      createdAt: new Date(),
      status: 'pending'
    };

    // Store job order
    this.commandHistory.set(jobOrderId, {
      ...jobOrder,
      type: 'manual'
    });

    return jobOrder;
  }

  /**
   * Generate specific instructions for manual gate operation
   * @param {Object} gate - Gate configuration
   * @returns {Array} - Array of instructions
   */
  generateGateInstructions(gate) {
    const instructions = [];
    
    // Safety check
    instructions.push('1. Verify area is clear of personnel and obstacles');
    instructions.push('2. Check upstream and downstream water levels');
    
    // Opening instructions
    if (gate.openTime) {
      instructions.push(`3. At ${gate.openTime}, open gate ${gate.gateName} to ${gate.targetHeight}cm`);
      instructions.push(`4. Monitor water flow and adjust if necessary`);
    }
    
    // Closing instructions
    if (gate.closeTime) {
      instructions.push(`5. At ${gate.closeTime}, close gate ${gate.gateName} to ${gate.currentHeight || 0}cm`);
      instructions.push(`6. Verify gate is properly sealed`);
    }
    
    // Final checks
    instructions.push('7. Record actual operation times and water levels');
    instructions.push('8. Report any issues or anomalies immediately');
    
    return instructions;
  }

  /**
   * Check status of a command
   * @param {string} commandId - Command ID
   * @returns {Promise<Object>} - Command status
   */
  async checkStatus(commandId) {
    const command = this.commandHistory.get(commandId);
    
    if (!command) {
      throw new Error(`Command ${commandId} not found`);
    }

    if (command.type === 'automatic' && command.scadaCommandId) {
      // Check SCADA status
      const scadaStatus = await checkCommandStatus(command.scadaCommandId);
      
      return {
        commandId,
        ...command,
        scadaStatus
      };
    }

    return command;
  }

  /**
   * Get all automatic gates configuration
   * @returns {Object} - Automatic gates configuration
   */
  getAutomaticGates() {
    return Object.entries(this.automaticGates).map(([alias, config]) => ({
      alias,
      stationCode: config.station_code,
      levels: config.levels,
      cumulativeLevels: config.cumulative_levels
    }));
  }

  /**
   * Get command history
   * @param {number} limit - Number of commands to return
   * @returns {Array} - Recent commands
   */
  getCommandHistory(limit = 50) {
    const commands = Array.from(this.commandHistory.values())
      .sort((a, b) => b.createdAt - a.createdAt)
      .slice(0, limit);
    
    return commands;
  }
}

module.exports = GateControlService;