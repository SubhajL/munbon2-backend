const WaterDemandIntegrationService = require('./water-demand-integration.service');
const GateLevelCalculatorService = require('./gate-level-calculator.service');
const GateControlService = require('./gate-control.service');
const IntegrationService = require('./integration.service');
const RealTimeAdjustmentService = require('./real-time-adjustment.service');
const MonitoringFeedbackService = require('./monitoring-feedback.service');
const controlFeedbackPublisher = require('./control-feedback-publisher');
const { v4: uuidv4 } = require('uuid');
const { 
  comprehensiveGateMapping, 
  getGatesBySection,
  getGatesByZone 
} = require('../config/comprehensive-gate-mapping');

class WaterControlOrchestratorService {
  constructor() {
    this.demandService = new WaterDemandIntegrationService();
    this.calculatorService = new GateLevelCalculatorService();
    this.gateControlService = new GateControlService();
    this.integrationService = new IntegrationService();
    this.adjustmentService = new RealTimeAdjustmentService();
    this.monitoringService = new MonitoringFeedbackService();
    
    // Tracking active operations
    this.activeOperations = new Map();
    
    // Gate network topology (should be loaded from database/config)
    this.gateMapping = this.loadGateMapping();
    
    // Set up event listeners for real-time adjustments
    this.setupEventListeners();
  }
  
  /**
   * Set up event listeners for monitoring and adjustments
   */
  setupEventListeners() {
    // Real-time adjustment events
    this.adjustmentService.on('adjustment_required', async (data) => {
      console.log(`Adjustment required for gate ${data.gate_name}: ${data.reason}`);
      await this.handleAdjustmentRequired(data);
    });
    
    this.adjustmentService.on('critical_alert', async (data) => {
      console.error(`Critical alert for operation ${data.operation_id}:`, data.alert);
      await this.handleCriticalAlert(data);
    });
    
    this.adjustmentService.on('emergency_adjustment', async (data) => {
      console.error(`Emergency adjustment required:`, data);
      await this.handleEmergencyAdjustment(data);
    });
    
    // Monitoring feedback events
    this.monitoringService.on('execution_completed', (data) => {
      console.log(`Execution completed for command ${data.tracking.command_id}`);
      this.updateOperationStatus(data);
    });
  }
  
  /**
   * Main orchestration method - converts demands to gate controls
   */
  async orchestrateWaterControl(zoneId, options = {}) {
    const operationId = uuidv4();
    console.log(`Starting water control orchestration ${operationId} for zone ${zoneId}`);
    
    try {
      // Track this operation
      this.activeOperations.set(operationId, {
        zone_id: zoneId,
        status: 'in_progress',
        started_at: new Date()
      });
      
      // Step 1: Get water demands and recommendations
      const demands = await this.demandService.generateGateRecommendations(zoneId, options);
      console.log(`Retrieved demands for ${demands.recommendations.length} sections`);
      
      // Step 2: Get current system state
      const systemState = await this.getCurrentSystemState(zoneId);
      
      // Step 3: Convert demands to gate requirements
      const gateRequirements = this.calculatorService.convertDemandsToGateRequirements(
        demands, 
        this.gateMapping
      );
      console.log(`Converted to ${gateRequirements.length} gate requirements`);
      
      // Step 4: Calculate gate settings
      const gateSettings = this.calculatorService.calculateMultipleGateSettings(gateRequirements);
      
      // Step 5: Optimize settings based on current state
      const optimizedSettings = this.calculatorService.optimizeGateSettings(
        gateSettings,
        systemState.current_gate_states
      );
      
      // Step 6: Validate settings
      const validation = this.calculatorService.validateGateSettings(
        optimizedSettings.individual_settings,
        { maxTotalFlow: systemState.available_flow }
      );
      
      if (!validation.valid) {
        throw new Error(`Gate settings validation failed: ${JSON.stringify(validation.errors)}`);
      }
      
      // Step 7: Generate control sequence
      const controlSequence = this.calculatorService.generateControlSequence(
        optimizedSettings,
        { baseDelay: options.operationDelay || 5 }
      );
      
      // Publish execution started event
      const totalGates = controlSequence.sequence.length;
      await controlFeedbackPublisher.publishExecutionStarted(operationId, zoneId, totalGates);
      
      // Step 8: Execute gate controls
      const executionResults = await this.executeGateControls(
        controlSequence,
        demands,
        { ...options, operationId }
      );
      
      // Step 9: Set up monitoring
      await this.setupMonitoring(operationId, executionResults, demands);
      
      // Update operation status
      this.activeOperations.set(operationId, {
        ...this.activeOperations.get(operationId),
        status: 'completed',
        completed_at: new Date(),
        results: executionResults
      });
      
      // Publish execution completed event
      const executionTime = new Date() - this.activeOperations.get(operationId).started_at;
      await controlFeedbackPublisher.publishExecutionCompleted(operationId, {
        zoneId: zoneId,
        weekStart: options.weekStart || new Date().toISOString().split('T')[0],
        totalGates: executionResults.summary.total_commands,
        successfulGates: executionResults.summary.successful,
        failedGates: executionResults.summary.failed,
        totalFlowRate: optimizedSettings.total_flow || 0,
        expectedDelivery: demands.summary.total_demand_m3,
        executionTimeMs: executionTime,
        batchId: options.batchId
      });
      
      return {
        operation_id: operationId,
        zone_id: zoneId,
        demands_summary: demands.summary,
        gate_settings: optimizedSettings,
        control_sequence: controlSequence,
        execution_results: executionResults,
        validation: validation,
        monitoring_enabled: true
      };
      
    } catch (error) {
      console.error(`Orchestration failed for operation ${operationId}:`, error);
      
      // Update operation status
      this.activeOperations.set(operationId, {
        ...this.activeOperations.get(operationId),
        status: 'failed',
        error: error.message,
        failed_at: new Date()
      });
      
      // Publish error event
      await controlFeedbackPublisher.publishControlError(operationId, {
        code: error.code || 'ORCHESTRATION_ERROR',
        message: error.message,
        zoneId: zoneId,
        severity: 'error'
      });
      
      // Attempt rollback if needed
      if (options.enableRollback) {
        await this.rollbackOperation(operationId);
      }
      
      throw error;
    }
  }
  
  /**
   * Get current system state including gate positions and water levels
   */
  async getCurrentSystemState(zoneId) {
    try {
      // Get current gate states from SCADA
      const gateStates = await this.integrationService.getCurrentGateStates();
      
      // Get water levels from sensors
      const waterLevels = await this.integrationService.getWaterLevels(zoneId);
      
      // Get available flow from source
      const sourceData = await this.integrationService.getSourceCapacity();
      
      return {
        current_gate_states: gateStates,
        water_levels: waterLevels,
        available_flow: sourceData.available_flow_m3s || 10.0, // Default 10 m³/s
        source_level: sourceData.water_level || 3.5, // Default 3.5m
        timestamp: new Date()
      };
    } catch (error) {
      console.error('Failed to get system state:', error);
      
      // Return defaults if services unavailable
      return {
        current_gate_states: {},
        water_levels: {},
        available_flow: 10.0,
        source_level: 3.5,
        timestamp: new Date()
      };
    }
  }
  
  /**
   * Execute gate controls based on sequence
   */
  async executeGateControls(controlSequence, demands, options = {}) {
    const results = {
      automatic_gates: [],
      manual_gates: [],
      summary: {
        total_commands: 0,
        successful: 0,
        failed: 0
      }
    };
    
    // Group gates by type
    const automaticGates = [];
    const manualGates = [];
    
    controlSequence.sequence.forEach(operation => {
      if (this.isAutomaticGate(operation.gate_name)) {
        automaticGates.push(operation);
      } else {
        manualGates.push(operation);
      }
    });
    
    // Process automatic gates
    for (const operation of automaticGates) {
      try {
        const result = await this.gateControlService.controlAutomaticGate({
          gateName: operation.gate_name,
          targetLevel: operation.target_level,
          reason: this.generateControlReason(operation, demands)
        });
        
        results.automatic_gates.push({
          ...result,
          operation_sequence: operation.sequence,
          scheduled_time: operation.scheduled_time,
          expectedFlow: operation.expected_flow_m3s
        });
        
        // Track execution for monitoring
        await this.monitoringService.trackCommandExecution({
          commandId: result.commandId,
          gateName: operation.gate_name,
          type: 'automatic',
          targetLevel: operation.target_level,
          expectedFlow: operation.expected_flow_m3s
        });
        
        // Publish gate update event
        await controlFeedbackPublisher.publishGateUpdated(
          results.operationId || options.operationId,
          operation.gate_name,
          'success',
          {
            command: 'set_level',
            openingMeters: operation.target_level,
            flowRate: operation.expected_flow_m3s
          }
        );
        
        results.summary.successful++;
        
        // Add delay between operations if specified
        if (options.operationDelay && operation.sequence < controlSequence.sequence.length) {
          await this.delay(options.operationDelay * 60 * 1000);
        }
      } catch (error) {
        console.error(`Failed to control gate ${operation.gate_name}:`, error);
        results.summary.failed++;
      }
    }
    
    // Create job order for manual gates
    if (manualGates.length > 0) {
      try {
        const jobOrder = await this.createManualGateJobOrder(manualGates, demands);
        results.manual_gates.push(jobOrder);
        results.summary.successful += manualGates.length;
      } catch (error) {
        console.error('Failed to create manual gate job order:', error);
        results.summary.failed += manualGates.length;
      }
    }
    
    results.summary.total_commands = automaticGates.length + manualGates.length;
    
    return results;
  }
  
  /**
   * Create job order for manual gates
   */
  async createManualGateJobOrder(manualOperations, demands) {
    const gates = manualOperations.map(op => {
      const section = this.findSectionForGate(op.gate_name);
      
      return {
        gateName: op.gate_name,
        location: this.getGateLocation(op.gate_name),
        zone: parseInt(section?.substring(3, 5) || '1'),
        currentHeight: 0, // Should get from current state
        targetHeight: Math.round(op.target_opening_cm),
        openTime: op.scheduled_time.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' }),
        closeTime: this.calculateCloseTime(op.scheduled_time, op.expected_flow_m3s),
        flow_m3s: op.expected_flow_m3s,
        priority: op.priority
      };
    });
    
    // Sort by zone and priority
    gates.sort((a, b) => {
      if (a.zone !== b.zone) return a.zone - b.zone;
      return b.priority - a.priority;
    });
    
    const jobOrder = await this.gateControlService.createManualGateJobOrder({
      operatorName: `Field Team Zone ${gates[0].zone}`,
      gates: gates,
      metadata: {
        demand_summary: demands.summary,
        total_flow_m3s: gates.reduce((sum, g) => sum + g.flow_m3s, 0),
        priority_sections: demands.stressed_areas.length
      }
    });
    
    return jobOrder;
  }
  
  /**
   * Set up monitoring for the operation
   */
  async setupMonitoring(operationId, executionResults, demands) {
    // Build monitoring configuration
    const expectedFlows = {};
    const targetLevels = {};
    
    executionResults.automatic_gates.forEach(gate => {
      expectedFlows[gate.gateName] = gate.expectedFlow || 0;
    });
    
    demands.recommendations.forEach(rec => {
      targetLevels[rec.section_id] = 1.0; // Default target level, should get from config
    });
    
    const monitoringConfig = {
      operation_id: operationId,
      gates: executionResults.automatic_gates.map(g => g.gateName),
      sections: demands.recommendations.map(r => r.section_id),
      expected_flows: expectedFlows,
      target_levels: targetLevels,
      check_interval: 60000, // 1 minute
      alert_thresholds: {
        flow_deviation_pct: 15,
        water_level_critical_pct: 30,
        response_time_ms: 300000 // 5 minutes
      }
    };
    
    // Start real-time monitoring
    this.adjustmentService.startMonitoring(operationId, monitoringConfig);
    
    console.log(`Real-time monitoring started for operation ${operationId}`);
    
    return monitoringConfig;
  }
  
  /**
   * Generate control reason for logging
   */
  generateControlReason(operation, demands) {
    const weeklyDemand = demands.summary.total_demand_m3;
    const prioritySections = demands.stressed_areas.length;
    
    let reason = `Weekly demand: ${Math.round(weeklyDemand)} m³`;
    
    if (prioritySections > 0) {
      reason += ` | ${prioritySections} stressed areas`;
    }
    
    if (operation.metadata?.flow_accuracy) {
      reason += ` | Flow accuracy: ${operation.metadata.flow_accuracy}%`;
    }
    
    return reason;
  }
  
  /**
   * Check if gate is automatic
   */
  isAutomaticGate(gateName) {
    const gateConfig = comprehensiveGateMapping[gateName];
    return gateConfig && gateConfig.type === 'automatic';
  }
  
  /**
   * Load gate network mapping
   */
  loadGateMapping() {
    // Build section-to-gates mapping from comprehensive configuration
    const sectionMapping = {};
    
    // Process all gates from comprehensive mapping
    Object.entries(comprehensiveGateMapping).forEach(([gateName, config]) => {
      if (config.sections && config.sections.length > 0) {
        config.sections.forEach(sectionId => {
          if (!sectionMapping[sectionId]) {
            sectionMapping[sectionId] = [];
          }
          sectionMapping[sectionId].push({
            gate_name: gateName,
            position: config.type === 'automatic' ? 'automatic' : 'manual',
            type: config.type,
            location: config.location,
            flow_coeff: config.flowCoeff,
            capacity_cms: config.capacity_cms
          });
        });
      }
    });
    
    return sectionMapping;
  }
  
  /**
   * Find section served by a gate
   */
  findSectionForGate(gateName) {
    for (const [section, gates] of Object.entries(this.gateMapping)) {
      if (gates.some(g => g.gate_name === gateName)) {
        return section;
      }
    }
    return null;
  }
  
  /**
   * Get gate physical location
   */
  getGateLocation(gateName) {
    const gateConfig = comprehensiveGateMapping[gateName];
    if (gateConfig && gateConfig.location) {
      return gateConfig.location;
    }
    return `${gateName} Canal`;
  }
  
  /**
   * Calculate gate close time based on flow and demand
   */
  calculateCloseTime(openTime, flowM3s) {
    // Simple calculation: 8 hours of operation
    const closeTime = new Date(openTime);
    closeTime.setHours(closeTime.getHours() + 8);
    
    return closeTime.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' });
  }
  
  /**
   * Rollback failed operation
   */
  async rollbackOperation(operationId) {
    console.log(`Attempting rollback for operation ${operationId}`);
    
    const operation = this.activeOperations.get(operationId);
    if (!operation || !operation.results) return;
    
    // Close any opened gates
    for (const gate of operation.results.automatic_gates || []) {
      try {
        await this.gateControlService.controlAutomaticGate({
          gateName: gate.gateName,
          targetLevel: 1, // Close to minimum
          reason: `Rollback operation ${operationId}`
        });
      } catch (error) {
        console.error(`Failed to rollback gate ${gate.gateName}:`, error);
      }
    }
  }
  
  /**
   * Utility delay function
   */
  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
  
  /**
   * Get operation status
   */
  getOperationStatus(operationId) {
    return this.activeOperations.get(operationId) || null;
  }
  
  /**
   * Get all active operations
   */
  getActiveOperations() {
    return Array.from(this.activeOperations.entries()).map(([id, op]) => ({
      operation_id: id,
      ...op
    }));
  }
  
  /**
   * Handle adjustment required event
   */
  async handleAdjustmentRequired(data) {
    const { operation_id, gate_name, adjustment, reason } = data;
    
    try {
      if (adjustment.type === 'level_change') {
        // Get current gate state
        const currentState = await this.integrationService.getCurrentGateStates();
        const currentLevel = currentState[gate_name]?.level || 1;
        const newLevel = Math.max(1, Math.min(4, currentLevel + adjustment.level_adjustment));
        
        // Execute adjustment
        const result = await this.gateControlService.controlAutomaticGate({
          gateName: gate_name,
          targetLevel: newLevel,
          reason: `Auto-adjustment: ${reason}`
        });
        
        console.log(`Executed adjustment for gate ${gate_name}: Level ${currentLevel} -> ${newLevel}`);
        
        // Track in monitoring
        await this.monitoringService.trackCommandExecution({
          commandId: result.commandId,
          gateName: gate_name,
          type: 'adjustment',
          targetLevel: newLevel,
          expectedFlow: adjustment.expected_flow
        });
      }
    } catch (error) {
      console.error(`Failed to execute adjustment for gate ${gate_name}:`, error);
    }
  }
  
  /**
   * Handle critical alert
   */
  async handleCriticalAlert(data) {
    const { operation_id, alert } = data;
    const operation = this.activeOperations.get(operation_id);
    
    if (!operation) return;
    
    // Log critical alert
    console.error(`CRITICAL: ${alert.type} in section ${alert.section_id}`);
    console.error(`Current level: ${alert.current_level}m, Target: ${alert.target_level}m`);
    
    // Update operation status
    operation.critical_alerts = (operation.critical_alerts || 0) + 1;
    operation.last_alert = alert;
    
    // Notify external systems if configured
    // This would integrate with your alert service
  }
  
  /**
   * Handle emergency adjustment
   */
  async handleEmergencyAdjustment(data) {
    const { operation_id, adjustments, reason } = data;
    
    console.error(`EMERGENCY: Executing ${adjustments.length} emergency adjustments`);
    
    // Execute all adjustments immediately
    const results = await Promise.allSettled(
      adjustments.map(async adj => {
        const currentState = await this.integrationService.getCurrentGateStates();
        const currentLevel = currentState[adj.gate_name]?.level || 1;
        const newLevel = Math.min(4, currentLevel + adj.target_increase);
        
        return this.gateControlService.controlAutomaticGate({
          gateName: adj.gate_name,
          targetLevel: newLevel,
          reason: `EMERGENCY: ${reason}`
        });
      })
    );
    
    const successful = results.filter(r => r.status === 'fulfilled').length;
    console.log(`Emergency adjustments: ${successful}/${adjustments.length} successful`);
  }
  
  /**
   * Update operation status based on monitoring feedback
   */
  updateOperationStatus(data) {
    const { tracking, verification, feedback } = data;
    const operation = Array.from(this.activeOperations.values())
      .find(op => op.results?.automatic_gates.some(g => g.commandId === tracking.command_id));
    
    if (operation) {
      operation.executed_commands = (operation.executed_commands || 0) + 1;
      operation.last_feedback = feedback;
      
      if (!verification.success) {
        operation.failed_commands = (operation.failed_commands || 0) + 1;
      }
    }
  }
  
  /**
   * Get monitoring report for operation
   */
  async getMonitoringReport(operationId) {
    const operation = this.activeOperations.get(operationId);
    if (!operation) return null;
    
    const realTimeStatus = this.adjustmentService.generateStatusReport(operationId);
    const performanceReport = this.monitoringService.generatePerformanceReport();
    
    return {
      operation: operation,
      real_time_status: realTimeStatus,
      performance: performanceReport,
      generated_at: new Date()
    };
  }
}

module.exports = WaterControlOrchestratorService;