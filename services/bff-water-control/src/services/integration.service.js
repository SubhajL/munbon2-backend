const axios = require('axios');
const winston = require('winston');

const logger = winston.createLogger({
  level: 'info',
  format: winston.format.json(),
  transports: [
    new winston.transports.Console({
      format: winston.format.simple()
    })
  ]
});

class IntegrationService {
  constructor() {
    this.services = {
      flowMonitoring: process.env.FLOW_MONITORING_URL,
      gravityOptimizer: process.env.GRAVITY_OPTIMIZER_URL,
      scheduledFieldOps: process.env.SCHEDULED_FIELD_OPS_URL,
      waterLevel: process.env.WATER_LEVEL_SERVICE_URL,
      alertService: process.env.ALERT_SERVICE_URL
    };
  }

  /**
   * Get water demand calculations from core services
   * @param {Object} params - Request parameters
   * @returns {Promise<Object>} - Water demand calculations
   */
  async getWaterDemandCalculations(params) {
    try {
      // Get flow monitoring data
      const flowData = await this.getFlowMonitoringData(params);
      
      // Get gravity optimization
      const gravityData = await this.getGravityOptimization(params);
      
      // Get scheduled operations
      const scheduledOps = await this.getScheduledOperations(params);
      
      // Combine results
      return {
        flowMonitoring: flowData,
        gravityOptimization: gravityData,
        scheduledOperations: scheduledOps,
        recommendations: this.generateRecommendations(flowData, gravityData, scheduledOps)
      };
    } catch (error) {
      logger.error('Failed to get water demand calculations:', error);
      throw error;
    }
  }

  /**
   * Get flow monitoring data
   * @param {Object} params - Request parameters
   * @returns {Promise<Object>} - Flow monitoring data
   */
  async getFlowMonitoringData(params) {
    try {
      const response = await axios.get(`${this.services.flowMonitoring}/api/v1/flow/current`, {
        params,
        timeout: 5000
      });
      
      return response.data;
    } catch (error) {
      logger.error('Failed to get flow monitoring data:', error);
      return null;
    }
  }

  /**
   * Get gravity optimization results
   * @param {Object} params - Request parameters
   * @returns {Promise<Object>} - Gravity optimization data
   */
  async getGravityOptimization(params) {
    try {
      const response = await axios.post(`${this.services.gravityOptimizer}/api/v1/optimize`, {
        ...params,
        mode: 'gravity_flow'
      }, {
        timeout: 10000
      });
      
      return response.data;
    } catch (error) {
      logger.error('Failed to get gravity optimization:', error);
      return null;
    }
  }

  /**
   * Get scheduled field operations
   * @param {Object} params - Request parameters
   * @returns {Promise<Object>} - Scheduled operations
   */
  async getScheduledOperations(params) {
    try {
      const response = await axios.get(`${this.services.scheduledFieldOps}/api/v1/operations/upcoming`, {
        params: {
          ...params,
          includeGates: true
        },
        timeout: 5000
      });
      
      return response.data;
    } catch (error) {
      logger.error('Failed to get scheduled operations:', error);
      return null;
    }
  }

  /**
   * Get current water levels
   * @param {Array} locations - Array of location IDs
   * @returns {Promise<Object>} - Water level data
   */
  async getWaterLevels(locations) {
    try {
      const response = await axios.post(`${this.services.waterLevel}/api/v1/levels/current`, {
        locations
      }, {
        timeout: 5000
      });
      
      return response.data;
    } catch (error) {
      logger.error('Failed to get water levels:', error);
      return null;
    }
  }

  /**
   * Send alert to alert service
   * @param {Object} alert - Alert data
   * @returns {Promise<Object>} - Alert response
   */
  async sendAlert(alert) {
    try {
      const response = await axios.post(`${this.services.alertService}/api/v1/alerts`, alert, {
        timeout: 5000
      });
      
      return response.data;
    } catch (error) {
      logger.error('Failed to send alert:', error);
      throw error;
    }
  }

  /**
   * Generate gate operation recommendations
   * @param {Object} flowData - Flow monitoring data
   * @param {Object} gravityData - Gravity optimization data
   * @param {Object} scheduledOps - Scheduled operations
   * @returns {Object} - Recommendations
   */
  generateRecommendations(flowData, gravityData, scheduledOps) {
    const recommendations = {
      automaticGates: [],
      manualGates: [],
      warnings: []
    };

    // Process gravity optimization results
    if (gravityData && gravityData.optimizedGateSettings) {
      gravityData.optimizedGateSettings.forEach(setting => {
        if (setting.isAutomatic) {
          recommendations.automaticGates.push({
            gateName: setting.gateName,
            targetLevel: setting.recommendedLevel,
            reason: 'Gravity optimization',
            priority: setting.priority || 'normal'
          });
        } else {
          recommendations.manualGates.push({
            gateName: setting.gateName,
            targetHeight: setting.recommendedHeight,
            openTime: setting.recommendedOpenTime,
            closeTime: setting.recommendedCloseTime,
            reason: 'Gravity optimization'
          });
        }
      });
    }

    // Check for conflicts with scheduled operations
    if (scheduledOps && scheduledOps.operations) {
      scheduledOps.operations.forEach(op => {
        const conflict = recommendations.automaticGates.find(rec => 
          rec.gateName === op.gateName && 
          Math.abs(new Date(op.scheduledTime) - new Date()) < 3600000 // Within 1 hour
        );
        
        if (conflict) {
          recommendations.warnings.push({
            type: 'scheduling_conflict',
            message: `Gate ${op.gateName} has conflicting operations`,
            details: { scheduled: op, recommended: conflict }
          });
        }
      });
    }

    // Add flow-based adjustments
    if (flowData && flowData.currentFlows) {
      flowData.currentFlows.forEach(flow => {
        if (flow.deviation > 0.2) { // 20% deviation
          recommendations.warnings.push({
            type: 'flow_deviation',
            message: `High flow deviation at ${flow.location}`,
            value: flow.deviation
          });
        }
      });
    }

    return recommendations;
  }

  /**
   * Test service connectivity
   * @returns {Promise<Object>} - Service status
   */
  async testConnectivity() {
    const status = {};
    
    for (const [name, url] of Object.entries(this.services)) {
      try {
        await axios.get(`${url}/health`, { timeout: 2000 });
        status[name] = 'connected';
      } catch (error) {
        status[name] = 'disconnected';
      }
    }
    
    return status;
  }
}

module.exports = IntegrationService;