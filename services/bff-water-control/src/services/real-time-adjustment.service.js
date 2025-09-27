const EventEmitter = require('events');

class RealTimeAdjustmentService extends EventEmitter {
  constructor() {
    super();
    
    // Active monitoring sessions
    this.monitoringSessions = new Map();
    
    // Adjustment thresholds
    this.thresholds = {
      flowDeviation: 0.15, // 15% deviation triggers adjustment
      waterLevelCritical: 0.30, // 30% below target is critical
      responseTime: 300000, // 5 minutes response time
      minAdjustmentInterval: 600000 // 10 minutes between adjustments
    };
    
    // Tracking adjustments
    this.adjustmentHistory = new Map();
  }
  
  /**
   * Start monitoring for an orchestration operation
   */
  startMonitoring(operationId, config) {
    console.log(`Starting real-time monitoring for operation ${operationId}`);
    
    const session = {
      operation_id: operationId,
      config: config,
      gates: new Map(),
      sections: new Map(),
      started_at: new Date(),
      active: true,
      adjustments: []
    };
    
    // Initialize gate monitoring
    config.gates.forEach(gateName => {
      session.gates.set(gateName, {
        expected_flow: config.expected_flows[gateName] || 0,
        last_reading: null,
        deviations: [],
        adjustments: 0
      });
    });
    
    // Initialize section monitoring
    config.sections.forEach(sectionId => {
      session.sections.set(sectionId, {
        target_level: config.target_levels[sectionId] || 1.0,
        last_reading: null,
        alerts: []
      });
    });
    
    this.monitoringSessions.set(operationId, session);
    
    // Start monitoring interval
    session.intervalId = setInterval(() => {
      this.performMonitoringCheck(operationId);
    }, config.check_interval || 60000); // Default 1 minute
    
    return session;
  }
  
  /**
   * Process sensor update
   */
  async processSensorUpdate(sensorData) {
    const { sensor_type, sensor_id, value, timestamp } = sensorData;
    
    // Find relevant monitoring sessions
    for (const [operationId, session] of this.monitoringSessions) {
      if (!session.active) continue;
      
      if (sensor_type === 'flow' && session.gates.has(sensor_id)) {
        await this.processFlowUpdate(operationId, sensor_id, value, timestamp);
      } else if (sensor_type === 'water_level' && session.sections.has(sensor_id)) {
        await this.processWaterLevelUpdate(operationId, sensor_id, value, timestamp);
      }
    }
  }
  
  /**
   * Process flow sensor update
   */
  async processFlowUpdate(operationId, gateName, flowValue, timestamp) {
    const session = this.monitoringSessions.get(operationId);
    const gateMonitor = session.gates.get(gateName);
    
    gateMonitor.last_reading = {
      value: flowValue,
      timestamp: timestamp
    };
    
    // Calculate deviation
    const expectedFlow = gateMonitor.expected_flow;
    const deviation = Math.abs(flowValue - expectedFlow) / expectedFlow;
    
    gateMonitor.deviations.push({
      deviation: deviation,
      timestamp: timestamp
    });
    
    // Check if adjustment needed
    if (deviation > this.thresholds.flowDeviation) {
      const adjustment = await this.calculateFlowAdjustment(
        gateName,
        expectedFlow,
        flowValue,
        gateMonitor
      );
      
      if (adjustment) {
        this.emit('adjustment_required', {
          operation_id: operationId,
          gate_name: gateName,
          adjustment: adjustment,
          reason: `Flow deviation: ${(deviation * 100).toFixed(1)}%`
        });
        
        gateMonitor.adjustments++;
        session.adjustments.push(adjustment);
      }
    }
  }
  
  /**
   * Process water level update
   */
  async processWaterLevelUpdate(operationId, sectionId, levelValue, timestamp) {
    const session = this.monitoringSessions.get(operationId);
    const sectionMonitor = session.sections.get(sectionId);
    
    sectionMonitor.last_reading = {
      value: levelValue,
      timestamp: timestamp
    };
    
    // Check critical level
    const targetLevel = sectionMonitor.target_level;
    const levelRatio = levelValue / targetLevel;
    
    if (levelRatio < (1 - this.thresholds.waterLevelCritical)) {
      // Critical low water level
      const alert = {
        type: 'critical_low_level',
        section_id: sectionId,
        current_level: levelValue,
        target_level: targetLevel,
        ratio: levelRatio,
        timestamp: timestamp
      };
      
      sectionMonitor.alerts.push(alert);
      
      this.emit('critical_alert', {
        operation_id: operationId,
        alert: alert
      });
      
      // Calculate emergency adjustment
      const adjustment = await this.calculateEmergencyAdjustment(
        operationId,
        sectionId,
        levelValue,
        targetLevel
      );
      
      if (adjustment) {
        this.emit('emergency_adjustment', adjustment);
      }
    }
  }
  
  /**
   * Calculate flow adjustment
   */
  async calculateFlowAdjustment(gateName, expectedFlow, actualFlow, gateMonitor) {
    // Check if too soon for another adjustment
    const lastAdjustment = this.getLastAdjustment(gateName);
    if (lastAdjustment) {
      const timeSince = Date.now() - lastAdjustment.timestamp;
      if (timeSince < this.thresholds.minAdjustmentInterval) {
        return null; // Too soon
      }
    }
    
    // Calculate required adjustment
    const flowDifference = expectedFlow - actualFlow;
    const adjustmentFactor = flowDifference / expectedFlow;
    
    // Determine gate level adjustment
    let levelAdjustment = 0;
    if (Math.abs(adjustmentFactor) > 0.3) {
      levelAdjustment = adjustmentFactor > 0 ? 1 : -1; // Major adjustment
    } else if (Math.abs(adjustmentFactor) > 0.15) {
      // Fine tuning - adjust opening percentage
      return {
        type: 'fine_tune',
        gate_name: gateName,
        opening_adjustment_pct: adjustmentFactor * 100,
        timestamp: new Date()
      };
    }
    
    if (levelAdjustment !== 0) {
      const adjustment = {
        type: 'level_change',
        gate_name: gateName,
        level_adjustment: levelAdjustment,
        reason: `Flow correction: ${flowDifference.toFixed(2)} m³/s`,
        expected_flow: expectedFlow,
        actual_flow: actualFlow,
        timestamp: new Date()
      };
      
      this.recordAdjustment(gateName, adjustment);
      return adjustment;
    }
    
    return null;
  }
  
  /**
   * Calculate emergency adjustment for critical water levels
   */
  async calculateEmergencyAdjustment(operationId, sectionId, currentLevel, targetLevel) {
    const session = this.monitoringSessions.get(operationId);
    
    // Find gates serving this section
    const affectedGates = [];
    for (const [gateName, config] of session.gates) {
      // This would use actual network topology
      // For now, assume all gates in session affect all sections
      affectedGates.push(gateName);
    }
    
    const levelDeficit = targetLevel - currentLevel;
    const deficitRatio = levelDeficit / targetLevel;
    
    return {
      type: 'emergency',
      operation_id: operationId,
      section_id: sectionId,
      affected_gates: affectedGates,
      adjustments: affectedGates.map(gate => ({
        gate_name: gate,
        action: 'increase_level',
        urgency: 'immediate',
        target_increase: Math.min(2, Math.ceil(deficitRatio * 4)) // Max 2 levels
      })),
      reason: `Critical water level: ${currentLevel.toFixed(2)}m (${(deficitRatio * 100).toFixed(1)}% deficit)`,
      timestamp: new Date()
    };
  }
  
  /**
   * Perform periodic monitoring check
   */
  async performMonitoringCheck(operationId) {
    const session = this.monitoringSessions.get(operationId);
    if (!session || !session.active) return;
    
    const now = Date.now();
    const alerts = [];
    
    // Check for stale data
    for (const [gateName, monitor] of session.gates) {
      if (!monitor.last_reading) {
        alerts.push({
          type: 'no_data',
          gate_name: gateName,
          message: 'No flow data received'
        });
      } else {
        const dataAge = now - new Date(monitor.last_reading.timestamp).getTime();
        if (dataAge > this.thresholds.responseTime) {
          alerts.push({
            type: 'stale_data',
            gate_name: gateName,
            message: `No updates for ${Math.round(dataAge / 60000)} minutes`
          });
        }
      }
    }
    
    // Check section status
    for (const [sectionId, monitor] of session.sections) {
      if (!monitor.last_reading) {
        alerts.push({
          type: 'no_data',
          section_id: sectionId,
          message: 'No water level data received'
        });
      }
    }
    
    if (alerts.length > 0) {
      this.emit('monitoring_alerts', {
        operation_id: operationId,
        alerts: alerts,
        timestamp: new Date()
      });
    }
    
    // Generate status report
    const report = this.generateStatusReport(operationId);
    this.emit('status_report', report);
  }
  
  /**
   * Generate monitoring status report
   */
  generateStatusReport(operationId) {
    const session = this.monitoringSessions.get(operationId);
    if (!session) return null;
    
    const gateStatus = [];
    for (const [gateName, monitor] of session.gates) {
      const deviation = monitor.deviations.length > 0
        ? monitor.deviations[monitor.deviations.length - 1].deviation
        : 0;
      
      gateStatus.push({
        gate_name: gateName,
        expected_flow: monitor.expected_flow,
        actual_flow: monitor.last_reading?.value || 0,
        deviation_pct: (deviation * 100).toFixed(1),
        adjustments: monitor.adjustments,
        status: deviation > this.thresholds.flowDeviation ? 'warning' : 'normal'
      });
    }
    
    const sectionStatus = [];
    for (const [sectionId, monitor] of session.sections) {
      const levelRatio = monitor.last_reading
        ? monitor.last_reading.value / monitor.target_level
        : 0;
      
      sectionStatus.push({
        section_id: sectionId,
        target_level: monitor.target_level,
        current_level: monitor.last_reading?.value || 0,
        level_ratio: levelRatio,
        alerts: monitor.alerts.length,
        status: levelRatio < 0.7 ? 'critical' : levelRatio < 0.85 ? 'warning' : 'normal'
      });
    }
    
    return {
      operation_id: operationId,
      duration_minutes: Math.round((Date.now() - session.started_at) / 60000),
      total_adjustments: session.adjustments.length,
      gate_status: gateStatus,
      section_status: sectionStatus,
      overall_status: this.calculateOverallStatus(gateStatus, sectionStatus),
      timestamp: new Date()
    };
  }
  
  /**
   * Calculate overall operation status
   */
  calculateOverallStatus(gateStatus, sectionStatus) {
    const criticalSections = sectionStatus.filter(s => s.status === 'critical').length;
    const warningGates = gateStatus.filter(g => g.status === 'warning').length;
    
    if (criticalSections > 0) {
      return 'critical';
    } else if (warningGates > gateStatus.length / 2) {
      return 'warning';
    } else if (warningGates > 0) {
      return 'attention';
    }
    
    return 'normal';
  }
  
  /**
   * Stop monitoring for an operation
   */
  stopMonitoring(operationId) {
    const session = this.monitoringSessions.get(operationId);
    if (!session) return;
    
    session.active = false;
    if (session.intervalId) {
      clearInterval(session.intervalId);
    }
    
    // Generate final report
    const finalReport = this.generateStatusReport(operationId);
    
    console.log(`Stopped monitoring for operation ${operationId}`);
    
    return finalReport;
  }
  
  /**
   * Record adjustment history
   */
  recordAdjustment(gateName, adjustment) {
    if (!this.adjustmentHistory.has(gateName)) {
      this.adjustmentHistory.set(gateName, []);
    }
    
    this.adjustmentHistory.get(gateName).push(adjustment);
    
    // Keep only last 100 adjustments per gate
    const history = this.adjustmentHistory.get(gateName);
    if (history.length > 100) {
      history.shift();
    }
  }
  
  /**
   * Get last adjustment for a gate
   */
  getLastAdjustment(gateName) {
    const history = this.adjustmentHistory.get(gateName);
    return history && history.length > 0 ? history[history.length - 1] : null;
  }
  
  /**
   * Get active monitoring sessions
   */
  getActiveSessions() {
    const active = [];
    for (const [operationId, session] of this.monitoringSessions) {
      if (session.active) {
        active.push({
          operation_id: operationId,
          started_at: session.started_at,
          gates_monitored: session.gates.size,
          sections_monitored: session.sections.size,
          total_adjustments: session.adjustments.length
        });
      }
    }
    return active;
  }
}

module.exports = RealTimeAdjustmentService;