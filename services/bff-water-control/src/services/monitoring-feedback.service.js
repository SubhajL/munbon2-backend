const EventEmitter = require('events');
const { connectToScadaDb } = require('../config/database');

class MonitoringFeedbackService extends EventEmitter {
  constructor() {
    super();
    
    // Performance metrics storage
    this.performanceMetrics = new Map();
    
    // Feedback queue for optimization services
    this.feedbackQueue = [];
    
    // Service endpoints for feedback
    this.feedbackEndpoints = {
      flow_monitoring: process.env.FLOW_MONITORING_URL || 'http://localhost:3044',
      gravity_optimizer: process.env.GRAVITY_OPTIMIZER_URL || 'http://localhost:3015',
      water_planning: process.env.WATER_PLANNING_URL || 'http://localhost:3007'
    };
    
    // Monitoring configuration
    this.config = {
      metricsRetentionDays: 30,
      feedbackBatchSize: 10,
      feedbackIntervalMs: 300000, // 5 minutes
      performanceThresholds: {
        delivery_efficiency_min: 0.80, // 80% minimum
        response_time_max: 600000, // 10 minutes max
        flow_accuracy_min: 0.85 // 85% accuracy
      }
    };
    
    // Start feedback processor
    this.startFeedbackProcessor();
  }
  
  /**
   * Track command execution
   */
  async trackCommandExecution(command) {
    const tracking = {
      command_id: command.commandId,
      gate_name: command.gateName,
      command_type: command.type || 'automatic',
      target_level: command.targetLevel,
      expected_flow: command.expectedFlow,
      started_at: new Date(),
      status: 'executing'
    };
    
    // Store in metrics
    if (!this.performanceMetrics.has(command.gateName)) {
      this.performanceMetrics.set(command.gateName, {
        total_commands: 0,
        successful_commands: 0,
        failed_commands: 0,
        average_response_time: 0,
        flow_accuracy_history: []
      });
    }
    
    const metrics = this.performanceMetrics.get(command.gateName);
    metrics.total_commands++;
    
    // Monitor execution
    this.monitorExecution(tracking);
    
    return tracking;
  }
  
  /**
   * Monitor command execution
   */
  async monitorExecution(tracking) {
    const checkInterval = setInterval(async () => {
      try {
        // Check SCADA status
        const status = await this.checkScadaCommandStatus(tracking.command_id);
        
        if (status.completed) {
          clearInterval(checkInterval);
          
          const executionTime = Date.now() - tracking.started_at;
          tracking.completed_at = new Date();
          tracking.execution_time_ms = executionTime;
          tracking.status = 'completed';
          
          // Verify actual vs expected
          const verification = await this.verifyExecution(tracking, status);
          
          // Update metrics
          this.updatePerformanceMetrics(tracking.gate_name, {
            success: verification.success,
            response_time: executionTime,
            flow_accuracy: verification.flow_accuracy
          });
          
          // Generate feedback
          const feedback = this.generateExecutionFeedback(tracking, verification);
          this.queueFeedback(feedback);
          
          // Emit completion event
          this.emit('execution_completed', {
            tracking,
            verification,
            feedback
          });
        }
      } catch (error) {
        console.error(`Failed to check command status: ${error.message}`);
      }
    }, 30000); // Check every 30 seconds
    
    // Timeout after 15 minutes
    setTimeout(() => {
      clearInterval(checkInterval);
      tracking.status = 'timeout';
      this.updatePerformanceMetrics(tracking.gate_name, {
        success: false,
        response_time: 900000
      });
    }, 900000);
  }
  
  /**
   * Check SCADA command status
   */
  async checkScadaCommandStatus(commandId) {
    const pool = await connectToScadaDb();
    
    try {
      const result = await pool.request()
        .query(`
          SELECT TOP 1 
            id,
            gate_name,
            gate_level,
            completestatus,
            DATEDIFF(SECOND, startdatetime, GETDATE()) as elapsed_seconds
          FROM tb_gatelevel_command
          WHERE id = ${commandId}
        `);
      
      if (result.recordset.length > 0) {
        const record = result.recordset[0];
        return {
          completed: record.completestatus === 1,
          elapsed_seconds: record.elapsed_seconds,
          actual_level: record.gate_level
        };
      }
      
      return { completed: false };
    } catch (error) {
      console.error('Failed to check SCADA status:', error);
      throw error;
    }
  }
  
  /**
   * Verify execution results
   */
  async verifyExecution(tracking, scadaStatus) {
    const verification = {
      success: true,
      expected_vs_actual: {},
      flow_accuracy: 1.0,
      issues: []
    };
    
    // Check if command completed successfully
    if (!scadaStatus.completed) {
      verification.success = false;
      verification.issues.push('Command did not complete');
    }
    
    // Check response time
    if (tracking.execution_time_ms > this.config.performanceThresholds.response_time_max) {
      verification.issues.push(`Slow response: ${Math.round(tracking.execution_time_ms / 1000)}s`);
    }
    
    // Get actual flow if available (would integrate with sensor data)
    if (tracking.expected_flow) {
      // This would fetch from sensor service
      const actualFlow = await this.getActualFlow(tracking.gate_name);
      
      if (actualFlow !== null) {
        verification.expected_vs_actual = {
          expected_flow: tracking.expected_flow,
          actual_flow: actualFlow,
          difference: actualFlow - tracking.expected_flow,
          difference_pct: ((actualFlow - tracking.expected_flow) / tracking.expected_flow * 100).toFixed(1)
        };
        
        verification.flow_accuracy = 1 - Math.abs(actualFlow - tracking.expected_flow) / tracking.expected_flow;
        
        if (verification.flow_accuracy < this.config.performanceThresholds.flow_accuracy_min) {
          verification.issues.push(`Low flow accuracy: ${(verification.flow_accuracy * 100).toFixed(1)}%`);
        }
      }
    }
    
    return verification;
  }
  
  /**
   * Update performance metrics
   */
  updatePerformanceMetrics(gateName, execution) {
    const metrics = this.performanceMetrics.get(gateName);
    if (!metrics) return;
    
    if (execution.success) {
      metrics.successful_commands++;
    } else {
      metrics.failed_commands++;
    }
    
    // Update average response time
    const totalCommands = metrics.successful_commands + metrics.failed_commands;
    metrics.average_response_time = 
      (metrics.average_response_time * (totalCommands - 1) + execution.response_time) / totalCommands;
    
    // Track flow accuracy
    if (execution.flow_accuracy !== undefined) {
      metrics.flow_accuracy_history.push({
        accuracy: execution.flow_accuracy,
        timestamp: new Date()
      });
      
      // Keep last 100 readings
      if (metrics.flow_accuracy_history.length > 100) {
        metrics.flow_accuracy_history.shift();
      }
    }
  }
  
  /**
   * Generate execution feedback
   */
  generateExecutionFeedback(tracking, verification) {
    const feedback = {
      id: `feedback_${Date.now()}_${tracking.command_id}`,
      timestamp: new Date(),
      gate_name: tracking.gate_name,
      command_id: tracking.command_id,
      execution_time_ms: tracking.execution_time_ms,
      success: verification.success,
      flow_accuracy: verification.flow_accuracy,
      issues: verification.issues,
      performance_data: verification.expected_vs_actual,
      recommendations: []
    };
    
    // Generate recommendations based on performance
    if (verification.flow_accuracy < 0.85) {
      feedback.recommendations.push({
        type: 'calibration',
        message: 'Gate flow coefficient may need recalibration',
        suggested_adjustment: verification.expected_vs_actual.difference_pct
      });
    }
    
    if (tracking.execution_time_ms > 300000) { // 5 minutes
      feedback.recommendations.push({
        type: 'maintenance',
        message: 'Gate response time is slow, maintenance may be required'
      });
    }
    
    return feedback;
  }
  
  /**
   * Queue feedback for batch processing
   */
  queueFeedback(feedback) {
    this.feedbackQueue.push(feedback);
    
    // Process immediately if batch size reached
    if (this.feedbackQueue.length >= this.config.feedbackBatchSize) {
      this.processFeedbackBatch();
    }
  }
  
  /**
   * Start feedback processor
   */
  startFeedbackProcessor() {
    setInterval(() => {
      if (this.feedbackQueue.length > 0) {
        this.processFeedbackBatch();
      }
    }, this.config.feedbackIntervalMs);
  }
  
  /**
   * Process feedback batch
   */
  async processFeedbackBatch() {
    if (this.feedbackQueue.length === 0) return;
    
    const batch = this.feedbackQueue.splice(0, this.config.feedbackBatchSize);
    console.log(`Processing feedback batch of ${batch.length} items`);
    
    // Group by service
    const serviceGroups = {
      flow_monitoring: [],
      gravity_optimizer: [],
      water_planning: []
    };
    
    batch.forEach(feedback => {
      // Route based on feedback type
      if (feedback.flow_accuracy !== undefined) {
        serviceGroups.flow_monitoring.push(feedback);
      }
      
      if (feedback.recommendations.some(r => r.type === 'calibration')) {
        serviceGroups.gravity_optimizer.push(feedback);
      }
      
      // All feedback goes to planning for historical analysis
      serviceGroups.water_planning.push(feedback);
    });
    
    // Send to services
    await Promise.all([
      this.sendFeedbackToService('flow_monitoring', serviceGroups.flow_monitoring),
      this.sendFeedbackToService('gravity_optimizer', serviceGroups.gravity_optimizer),
      this.sendFeedbackToService('water_planning', serviceGroups.water_planning)
    ]);
  }
  
  /**
   * Send feedback to service
   */
  async sendFeedbackToService(service, feedbackItems) {
    if (feedbackItems.length === 0) return;
    
    const endpoint = this.feedbackEndpoints[service];
    if (!endpoint) return;
    
    try {
      const axios = require('axios');
      await axios.post(`${endpoint}/api/v1/feedback`, {
        feedback: feedbackItems,
        source: 'water-control-bff',
        timestamp: new Date()
      });
      
      console.log(`Sent ${feedbackItems.length} feedback items to ${service}`);
    } catch (error) {
      console.error(`Failed to send feedback to ${service}:`, error.message);
      
      // Re-queue failed items
      feedbackItems.forEach(item => this.feedbackQueue.push(item));
    }
  }
  
  /**
   * Get actual flow from sensors (mock implementation)
   */
  async getActualFlow(gateName) {
    // This would integrate with sensor service
    // For now, return simulated value
    const baseFlow = this.performanceMetrics.get(gateName)?.last_expected_flow || 2.0;
    const variation = (Math.random() - 0.5) * 0.3; // ±15% variation
    return baseFlow * (1 + variation);
  }
  
  /**
   * Generate performance report
   */
  generatePerformanceReport(gateName = null) {
    const report = {
      generated_at: new Date(),
      gates: []
    };
    
    const gatesToReport = gateName 
      ? [gateName] 
      : Array.from(this.performanceMetrics.keys());
    
    gatesToReport.forEach(gate => {
      const metrics = this.performanceMetrics.get(gate);
      if (!metrics) return;
      
      const successRate = metrics.total_commands > 0
        ? metrics.successful_commands / metrics.total_commands
        : 0;
      
      const avgFlowAccuracy = metrics.flow_accuracy_history.length > 0
        ? metrics.flow_accuracy_history.reduce((sum, h) => sum + h.accuracy, 0) / metrics.flow_accuracy_history.length
        : 1.0;
      
      report.gates.push({
        gate_name: gate,
        total_commands: metrics.total_commands,
        success_rate: (successRate * 100).toFixed(1),
        average_response_time_ms: Math.round(metrics.average_response_time),
        average_flow_accuracy: (avgFlowAccuracy * 100).toFixed(1),
        recent_accuracy_trend: this.calculateAccuracyTrend(metrics.flow_accuracy_history),
        performance_score: this.calculatePerformanceScore(metrics)
      });
    });
    
    // Sort by performance score
    report.gates.sort((a, b) => b.performance_score - a.performance_score);
    
    return report;
  }
  
  /**
   * Calculate accuracy trend
   */
  calculateAccuracyTrend(history) {
    if (history.length < 10) return 'insufficient_data';
    
    const recent = history.slice(-10);
    const older = history.slice(-20, -10);
    
    const recentAvg = recent.reduce((sum, h) => sum + h.accuracy, 0) / recent.length;
    const olderAvg = older.reduce((sum, h) => sum + h.accuracy, 0) / older.length;
    
    const change = recentAvg - olderAvg;
    
    if (change > 0.05) return 'improving';
    if (change < -0.05) return 'degrading';
    return 'stable';
  }
  
  /**
   * Calculate overall performance score
   */
  calculatePerformanceScore(metrics) {
    const successRate = metrics.total_commands > 0
      ? metrics.successful_commands / metrics.total_commands
      : 1.0;
    
    const responseScore = Math.max(0, 1 - metrics.average_response_time / this.config.performanceThresholds.response_time_max);
    
    const accuracyScore = metrics.flow_accuracy_history.length > 0
      ? metrics.flow_accuracy_history.reduce((sum, h) => sum + h.accuracy, 0) / metrics.flow_accuracy_history.length
      : 1.0;
    
    // Weighted average
    return (successRate * 0.4 + responseScore * 0.3 + accuracyScore * 0.3) * 100;
  }
  
  /**
   * Clean old metrics
   */
  cleanOldMetrics() {
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - this.config.metricsRetentionDays);
    
    for (const [gateName, metrics] of this.performanceMetrics) {
      // Clean old accuracy history
      metrics.flow_accuracy_history = metrics.flow_accuracy_history.filter(
        h => h.timestamp > cutoffDate
      );
    }
  }
}

module.exports = MonitoringFeedbackService;